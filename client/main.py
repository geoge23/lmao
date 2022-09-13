import os
import serial
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap, QMovie
from PyQt5.QtCore import Qt, QThread, pyqtSlot as Slot, pyqtSignal as Signal, QTimer, QObject, QEvent
from functools import partial
import requests as req
import re
import time
import sys

#mocks the requests import to add the Authorization header to all outgoing requests
requests = req.session()
requests.headers["Authorization"] = "Bearer {}".format(os.getenv("KEY"))

SERVER_URL=os.getenv("URL") or "http://localhost:5000"
#qss for warning message boxes
MESSAGE_BOX_QSS = """
                QLabel {
                    color: white; 
                    font-size: 20;
                } 
                QPushButton { 
                    background-color: #496499; 
                    border: none; 
                    color: #ffffff; 
                    font-size: 18px; 
                    font-weight: bold; 
                    padding: 4;
                } 
                QMessageBox {
                    background-color: #393939;
                }
            """

# This class handles the router and state for the application
# It takes in the main window widget and controls the QStackedWidget
# We use a QStackedWidget to switch between different screens in lieu of
# a true router system like found in other frameworks
class ApplicationController:
    def __init__(self, view):
        self.view = view
        self.widgets = {}
        self.current_widget = ""
        self.user_info = {}
        self.logged_in = False
        self.last_click = time.time()

        #this timer checks for inactivity every second (1000ms)
        timer = QTimer(self.view.widget)
        timer.timeout.connect(self.handle_timeout_timer)
        timer.start(1000)

    #sets last click to current time
    def set_last_click(self):
        self.last_click = time.time()
    
    def handle_timeout_timer(self):
        #Time out user after 180 seconds of inactivity (3 minutes)
        if time.time() - self.last_click > 180:
            self.set_last_click()
            if self.logged_in:
                self.log_out()

    def set_user_info(self, info):
        self.user_info = info
        self.logged_in = True
        self.set_last_click()

    def get_username(self):
        return self.user_info.get("name", "")

    #Sets up the interface for another user
    #Clears their UserInfo and logs them out, then removes widgets from the router
    def log_out(self):
        self.user_info = {}
        for _, w in self.widgets.items():
            self.view.stack.removeWidget(w["component"])
        self.widgets = {}
        self.go_to_widget(StartScreen)

    #The workhorse function of the router system
    #Used to navigate to (and rerender) routes
    def go_to_widget(self, page, *args):
        #check if the page class is already in the router
        if page.__name__ in self.widgets:
            #if it is, just switch to it
            idx = self.widgets[page.__name__]["index"]
            self.view.stack.setCurrentIndex(idx)
        else:
            #if it isn't, create a new widget and add it to the router
            #you can pass args to the constructor of the widget from the 
            #go-to-widget function, just like params in the browser
            #also passes it the application controller for navigation away from that page
            component = page(self, *args)
            self.view.stack.addWidget(component)
            #gets the index of the new widget by getting the length of the router
            #items are always added to the end of the router
            idx = self.view.stack.count() - 1
            self.widgets[page.__name__] = {"index": idx, "component": component}
            self.view.stack.setCurrentIndex(idx)

        #if the current widget has should_refresh set to true, remove it so it is re-rendered on the next visit
        #good for things with user-specific data like the user's name or checkouts
        if self.current_widget != "" and self.current_widget in self.widgets and getattr(self.widgets[self.current_widget]["component"], "should_refresh", False):
            try:
                #call this function if it exists, allows for final shutdown (i.e. closing of serial connection)
                self.widgets[self.current_widget]["component"].on_remove()
            except:
                pass
            self.view.stack.removeWidget(self.widgets[self.current_widget]["component"])
            del self.widgets[self.current_widget]

        self.current_widget = page.__name__
        
#This class shows a loading gif in a window, useful for actions that take time
#will only display full gif if action takes place in another thread, i.e. Requester
class LoadWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setFixedSize(150,150)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: #383838")

        self.setWindowState(Qt.WindowActive)

        icon = QMovie('assets/loading.gif')
        image = QLabel()
        image.setMovie(icon)
        icon.start()
        image.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(image)

    def show(self):
        super().show()

        self.setWindowState(Qt.WindowActive)

#This class is for the thread to listen for the scanner via serial connection
class ScannerController(QThread):
    item = Signal(str)

    def run(self):
        self.serial = serial.Serial(os.getenv('SCANNER_SERIAL_PORT'))
        while self.serial.is_open:
            try:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode()
                    if line.strip("\r\n"):
                        self.item.emit(line.strip("\r\n"))
            except:
                #ignores weird errors with serial closing. If there's weird problems, try catching the error that gets ignored here!
                pass

#This class is for the thread to poll the RFID reader via serial connection
class RfidController(QThread):
    found = Signal(tuple)

    def run(self):
        self.serial = serial.Serial(os.getenv('RFID_SERIAL_PORT'))
        #Send settings to RFID reader and clear the last read card (in case one was scanned before we start polling)
        self.serial.write(b"rfid:cmd.echo=0\nrfid:cmd.prompt=0\nrfid:qid.id.hold\n")
        self.serial.reset_input_buffer()
        while self.serial.is_open:
            #request a card
            self.serial.write(b"rfid:qid.id\n")
            #read the data from the request
            line = self.serial.readline()
            while line == b'\r\n' or line == b'\n':
                #ignore empty lines
                line = self.serial.readline()
            
            try:
                #a response looks like {0x00BB,1,0x0000,80;0x000000801CD1931B2F14}, we want the number stored in the last index
                #more available at https://www.rfideas.com/sites/default/files/2020-01/ASCII_Manual.pdf
                sanitized_data = re.sub("[{}\r\n]", "", line.decode())
                card_info = sanitized_data.split(',')
                #checks if the card has not been at the reader for more than 2 seconds and ignores if so
                #divided by 48 because time is in intervals of 48ms
                if int(card_info[0], 16) > (2000 / 48):
                    time.sleep(0.5)
                    continue
                card_id_string = card_info[3].split(';')[1]
                card_id = int(card_id_string, 16)
                #0 means no card read, so ignore
                if card_id == 0:
                    time.sleep(0.5)
                    continue
                else:
                    #at some point, this could be transitioned to the Requester class to make it follow after the similar system in the barcode scanner class
                    #but for now, we'll just emit the user info after the card is read and info is pulled

                    #emits tuple, (does user exist, user info)
                    info = requests.get(SERVER_URL + "/user", params={"gtid": card_id})
                    if info.status_code != 200:
                        self.found.emit((False, {"gtid": card_id}))
                    else:
                        self.found.emit((True, info.json()))
                    self.serial.close()
            except:
                pass

#This class is for the thread to make blocking HTTP requests to the server outside of the main thread
#It drastically improves UX and allows for loaders to be displayed while requesting data
class Requester(QThread):
    complete = Signal(req.Response)

    def __init__(self, e, method, path, **kwargs):
        #e is a reference to the class this runs in, so we can set it as the parent of this thread
        super().__init__(e)

        self.method = method
        self.path = path

        self.kwargs = kwargs

    def run(self):
        #gets the function to make the request (i.e. requests.get, requests.post, etc)
        method = getattr(requests, self.method)
        #and makes it with any args passed to the constructor
        req = method(SERVER_URL + self.path, **self.kwargs)
        self.complete.emit(req)

#main window, contains the stack of widgets controlled by ApplicationController
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("EOSL Inventory Management")
        self.setFixedSize(800,480)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.layout = QVBoxLayout()
        self.widget = QWidget()
        self.widget.setLayout(self.layout)

        self.stack = QStackedWidget()

        self.layout.addWidget(self.stack)

        self.setCentralWidget(self.widget)

#Start screen, shows the logo
class StartScreen(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        #this is the convention for the main layout storage throughout the app
        #when expanding, try to stick to having the primary component layout be stored as 
        #an instance variable called self.l
        self.l = QVBoxLayout()
        self.l.setAlignment(Qt.AlignHCenter)
        self.setLayout(self.l)
        self.l.addStretch()

        logo = QPixmap('assets/gt-logo.png').scaled(150, 150, Qt.KeepAspectRatio)
        image = QLabel()
        image.setPixmap(logo)
        image.setAlignment(Qt.AlignHCenter)
        self.l.addWidget(image)

        title = QLabel("Lab Management Asset Organizer")
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet("font-weight: bold;")
        self.l.addWidget(title)

        subtext = QLabel("Scan ID to begin")
        subtext.setAlignment(Qt.AlignHCenter)
        subtext.setStyleSheet("font-weight: light;")
        self.l.addWidget(subtext)
        self.l.addStretch()

        #Before starting to scan for RFID cards, make sure we can talk to the server
        #if not, throw an error and die
        try:
            if requests.get(SERVER_URL + "/ping").status_code == 200:
                t = RfidController(self)
                t.found.connect(self.next_page)
                t.start()
            else:
                #can connect but auth failed
                msg = QMessageBox(QMessageBox.Icon.Critical, "", "Error Authenticating with Server")
                msg.setInformativeText("Check that your API key is valid then press OK to restart the client")
                msg.setWindowFlags(Qt.FramelessWindowHint)
                msg.setStyleSheet(MESSAGE_BOX_QSS)
                msg.exec()
                sys.exit(111)
        except Exception as e:
            #can't connect at all
            msg = QMessageBox(QMessageBox.Icon.Critical, "", "Error Contacting Server")
            msg.setInformativeText("Check that the server is on and running then press OK to restart the client")
            msg.setWindowFlags(Qt.FramelessWindowHint)
            msg.setStyleSheet(MESSAGE_BOX_QSS)
            msg.exec()
            sys.exit(111)

    #handle the tuple emitted from RfidController by beginning the login process
    #user_doc looks like (does user exist, user info)
    def next_page(self, user_doc):
        if user_doc[0] == False:
            #doesn't exist, so show the create user screen and pass the GTID of the new user
            self.controller.go_to_widget(NameScreen, user_doc[1]["gtid"])
        else:
            self.controller.set_user_info(user_doc[1])
            self.controller.go_to_widget(MainScreen)

#creates the buttons you see on the main screen with the large icons
def build_large_action_button(text, image, action = None):
    button = QWidget()
    button.setStyleSheet("background-color: #496499")
    button.setFixedSize(200,250)
    layout = QVBoxLayout()
    button.setLayout(layout)

    #overrides the mouse press handler for this widget
    #make sure you understand the implications of this before you use it 
    #read the Qt docs about mousePressEvents, this is not the same as the clicked signal on buttons

    #should migrate this system to a custom signal to mimic the clicked api on actual buttons in the future
    if action != None:
        button.mousePressEvent = action

    icon = QPixmap(image).scaled(100, 100, Qt.KeepAspectRatio)
    image = QLabel()
    image.setPixmap(icon)
    image.setAlignment(Qt.AlignHCenter)
    layout.addWidget(image)

    layout.setAlignment(Qt.AlignCenter)
    cap = QLabel(text)
    cap.setStyleSheet("font-weight: bold;")
    layout.addWidget(cap)
    return button

#the main screen of the application, allows you to navigate to other screens
class MainScreen(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.l.setAlignment(Qt.AlignTop)

        title = QLabel("Welcome, {}".format(controller.get_username()))
        self.l.addWidget(title)

        self.l.addStretch()

        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignHCenter)
        button_layout.addWidget(build_large_action_button("Check out items", "assets/menu.png", partial(self.go_to_pg, ScanOutScreen)))
        button_layout.addWidget(build_large_action_button("Return items", "assets/checkout.png", partial(self.go_to_pg, ScanInScreen)))
        button_layout.addWidget(build_large_action_button("View items out", "assets/return.png", partial(self.go_to_pg, ItemsOutScreen)))
        self.l.addLayout(button_layout) 

        self.l.addStretch()
        log_out = QPushButton("Log off")
        log_out.clicked.connect(self.controller.log_out)
        self.l.addWidget(log_out)

    #an example of something to override the mousePressEvent for a widget
    def go_to_pg(self, page, ev):
        if ev.button() == Qt.LeftButton:
            ev.accept()
            self.controller.go_to_widget(page)
        else:
            return QWidget.mousePressEvent(self, ev)

#the backbone of all pages in the application, shows the ui with a list, buttons, and title
class BaseTransactionScreen(QWidget):
    def __init__(self, controller, title_text, empty_text="This list is empty"):
        super().__init__()

        self.controller = controller

        self.l = QVBoxLayout()
        self.setLayout(self.l)
        self.l.setAlignment(Qt.AlignTop)

        title = QLabel(title_text)
        title.setStyleSheet("font-weight: bold;")
        self.l.addWidget(title)

        self.items = QVBoxLayout()
        self.items.setAlignment(Qt.AlignHCenter)

        self.empty_text = QLabel(empty_text)
        self.empty_text.setStyleSheet("color: white; font-size: 18;")
        self.items.addWidget(self.empty_text)

        widget = QWidget()
        widget.setLayout(self.items)
        
        scroller = QScrollArea()
        scroller.setWidget(widget)
        scroller.setStyleSheet("background-color: transparent; border: none;")

        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroller.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroller.setAlignment(Qt.AlignTop)
        scroller.setWidgetResizable(True)
        #allows this to be scrolled with a swipe instead of the (now hidden) scrollbar
        QScroller.grabGesture(scroller, QScroller.LeftMouseButtonGesture)

        self.l.addWidget(scroller)
        
        self.buttons = QHBoxLayout()
        self.buttons.addStretch()
        self.l.addLayout(self.buttons)
    
    #called when something is added to the list, removes the placeholder text
    def _remove_empty_text(self):
        if self.empty_text != None:
            self.empty_text.deleteLater()
            self.empty_text = None

    def create_action_button(self, text, action = None, stylesheet = None):
        button = QPushButton(text)
        if action is not None: button.clicked.connect(action)
        if stylesheet is not None: button.setStyleSheet(stylesheet)
        self.buttons.addWidget(button)

    def create_entry(self, text, action = None, under_text=None, side_text=None, image=None):
        self._remove_empty_text()
        entry = QWidget()
        spread = QHBoxLayout()
        entry.setLayout(spread)

        textArea = QVBoxLayout()
        top_text = QLabel(text)
        top_text.setStyleSheet("font-size: 18px; font-weight: bold;")
        textArea.addWidget(top_text)
        textArea.addWidget(QLabel(under_text)) if under_text != None else ""
        spread.addLayout(textArea)
        spread.addStretch()
        
        #uses Requester to download image by ID included in the call to create_entry
        if image:
            img_label = QLabel()
            img_label.setAlignment(Qt.AlignHCenter)
            spread.addWidget(img_label)

            #defines a function to add the image once the request finishes
            #this is later passed into the Requester as a callback
            def on_req_complete(img_label, downloaded_img):
                icon = QPixmap()
                icon.loadFromData(downloaded_img.content)
                icon = icon.scaled(60, 60, Qt.KeepAspectRatio)
                img_label.setPixmap(icon)

            #all images in the system follow this pattern for access
            req = Requester(self, "get", "/image/{}".format(image))
            #use a partial to give the callback access to the label to hold the image
            req.complete.connect(partial(on_req_complete, img_label))
            req.start()
        #adds the side text only if no image exists
        else:
            spread.addWidget(QLabel(side_text)) if side_text != None else ""

        entry.setMaximumWidth(500)
        entry.setMaximumHeight(75)
        entry.setStyleSheet("background-color: #D9D9D9; color: black;")

        self.items.addWidget(entry)

    def create_heading(self, text):
        entry = QWidget()
        spread = QHBoxLayout()
        entry.setLayout(spread)

        textArea = QVBoxLayout()
        top_text = QLabel(text)
        top_text.setStyleSheet("font-size: 22px; font-weight: bold;")
        textArea.addWidget(top_text)
        spread.addLayout(textArea)
        spread.addStretch()

        entry.setMaximumWidth(500)
        entry.setMaximumHeight(45)
        entry.setStyleSheet("color: white;")

        self.items.addWidget(entry)

#allows for entry of new users
class NameScreen(BaseTransactionScreen):
    should_refresh = True

    #gets a new user's GTID from the prop passed by StartScreen when it switches to this window
    def __init__(self, controller, gtid):
        super().__init__(controller, title_text="Create your Account")
        self.controller = controller
        self.gtid = gtid
        self._remove_empty_text()
        
        area1 = QHBoxLayout()
        nameHere = QLabel("Name:")
        nameHere.setStyleSheet("font-size: 15pt")
        area1.addWidget(nameHere)
        userName = QTextEdit()
        userName.setFixedSize(650, 30)
        userName.setStyleSheet("background-color: #496499; color: white; font-size: 12pt")
        area1.addWidget(userName)
        area1.addStretch()
        
        area2 = QHBoxLayout()
        emailHere = QLabel("Email: ")
        emailHere.setStyleSheet("font-size: 15pt")
        area2.addWidget(emailHere)
        userEmail = QTextEdit()
        userEmail.setFixedSize(500, 30)
        userEmail.setStyleSheet("background-color: #496499; color: white; font-size: 12pt")
        area2.addWidget(userEmail)
        area2.addWidget(QLabel("@gtri.gatech.edu"))
        area2.addStretch()

        self.items.addLayout(area1)
        self.items.addLayout(area2)
        self.create_action_button("Cancel", action=lambda: controller.go_to_widget(StartScreen))

        self.create_action_button("Continue", action = partial(self.startRequest, userName, userEmail))

    #validates and then sends new user to the server for creation
    def startRequest(self, userName, userEmail):
        if userName.toPlainText() == "" or userEmail.toPlainText() == "":
            msg = QMessageBox(QMessageBox.Icon.Warning, "Invalid Request", "Fields are missing")
            msg.setWindowFlags(Qt.FramelessWindowHint)
            msg.setStyleSheet(MESSAGE_BOX_QSS)
            msg.exec()
            return
        new_user_dict = {"name": userName.toPlainText(), "gtid": self.gtid, "email": userEmail.toPlainText() + "@gtri.gatech.edu"}
        requester = Requester(self, "post", "/user", json = new_user_dict)
        loader = LoadWindow()
        loader.show()
        requester.complete.connect(partial(self.endRequest, new_user_dict, loader))
        requester.start()

    #when the the server finishes creating the user, take the doc and save it to the local state
    #the _ is to ignore the response data from the server, since it's not needed
    def endRequest(self, new_user_dict, loader, _):
        self.controller.set_user_info(new_user_dict)
        self.controller.go_to_widget(MainScreen)
        loader.close()

#inherits from the BaseTransactionScreen to make the "currently checked out items" screen
class ItemsOutScreen(BaseTransactionScreen):
    should_refresh = True

    def __init__(self, controller):
        super().__init__(controller, title_text="Your checked out items", empty_text="You have no items checked out")
        self.create_action_button("Main Menu", action=lambda: controller.go_to_widget(MainScreen))
        
        self.load = LoadWindow()
        self.load.show()
        request = Requester(self, "get", "/user/items", params={"gtid": self.controller.user_info["gtid"]})
        request.complete.connect(self.getItemsCallback)

        request.start()
        
    def getItemsCallback(self, items):
        for item in items.json():
            self.create_entry(item['name'], under_text="As of {}".format(item["start_date"]), side_text="Located at {}".format(item['area']) if item['area'] else "", image=item['image'])
        self.load.close()

#this class is building on the BaseTransactionScreen to make the check in and out screens
class BaseScanScreen(BaseTransactionScreen):
    should_refresh = True

    def __init__(self, controller, title_text, request_builder):
        super().__init__(controller, title_text=title_text, empty_text="Scan items and press Done to continue")
        
        self.create_action_button("Cancel", action=lambda: controller.go_to_widget(MainScreen))
        self.create_action_button("Done", action=self.check_out_items)

        self.request_builder = request_builder

        self.current_items = []
        self.requests = []
        
        #picks up incoming barcodes from the scanner
        self.scanner = ScannerController(self)
        self.scanner.item.connect(self.item_scanned)

        self.scanner.start()
        

    def item_scanned(self, barcode):
        requester = Requester(self, "get", "/item", params={"barcode": barcode})

        self.requests.append(requester)

        load = LoadWindow()
        load.show()
        requester.complete.connect(partial(self.on_request_complete, requester, load))
        requester.start()

    def on_request_complete(self, requester, load_screen, b):
        load_screen.close()
        self.requests.remove(requester)

        api_response = b.json()
        #adds all items returned from the api response
        for item in api_response:
            if not next((el for el in self.current_items if el["id"] == item["id"]), False):
                self.current_items.append(item)
                self.create_entry(item["name"], under_text="Located in {}".format(item['area']) if item['area'] else "Barcode: {}".format(item["barcode"]), image=item['image'])

    #wait for all requests to finish before deleting the widget and navigating away
    def on_remove(self):
        for req in self.requests:
            req.wait()

        #close the scanner serial and kill the thread
        #another sticeking point, this seems to cause problems especially when testing on Windows
        self.scanner.serial.close()
        self.scanner.quit()

    #when user finishes, call the request builder to build the request and send it to the server
    #then, display the results in a receipt screen
    def check_out_items(self):
        error_items = []
        success_items = []

        #error out if no items are scanned to check out/in
        if len(self.current_items) == 0:
            msg = QMessageBox(QMessageBox.Icon.Warning, "Invalid Request", "No items selected!")
            msg.setWindowFlags(Qt.FramelessWindowHint)
            msg.setStyleSheet(MESSAGE_BOX_QSS)
            msg.exec()
            return
        
        #start loading
        self.load = LoadWindow()
        self.load.show()

        #callback for requests when they finish
        def checkout_request_done(self, requester, item, data):
            self.requests.remove(requester)
            
            if data.status_code != 200:
                item.update({"error": data.json()['error']})
                error_items.append(item)
            else:
                if data.json().get("message", None):
                    item.update({"message": data.json()['message']})
                success_items.append(item)

            #close the load screen if all requests are done, then go to the Receipt screen
            if len(self.requests) == 0:
                self.load.close()
                self.controller.go_to_widget(TransactionCompleteScreen, error_items, success_items)

        #send a request from the builder for each item
        #NEEDS to be implemented in the subclass, this class does not work standalone
        for item in self.current_items:
            requester = self.request_builder(item)
            self.requests.append(requester)

            requester.complete.connect(partial(checkout_request_done, self, requester, item))

            requester.start()

class ScanOutScreen(BaseScanScreen):
    def __init__(self, controller):
        super().__init__(controller, "Check out items", self.build_request)

    #builds a requester object to check out an item when given the item object
    def build_request(self, item):
        return Requester(self, "post", "/checkout", json={"barcode": item["barcode"], "gtid": self.controller.user_info["gtid"]})

class ScanInScreen(BaseScanScreen):
    def __init__(self, controller):
        super().__init__(controller, "Check in items", self.build_request)

    #builds a requester object to check in an item when given the item object
    def build_request(self, item):
        return Requester(self, "delete", "/checkout", json={"barcode": item["barcode"], "gtid": self.controller.user_info["gtid"]})


#shows a receipt screen when a transaction is complete
class TransactionCompleteScreen(BaseTransactionScreen):
    should_refresh = True

    def __init__(self, controller, error_item, normal_item):
        super().__init__(controller, title_text="Your Receipt")
        
        self.create_action_button("Continue", action=lambda: controller.go_to_widget(MainScreen))
        self.create_action_button("Sign Out", action=lambda: controller.log_out())

        if len(error_item) > 0: self.create_heading("Items with Errors")
        for i in error_item:
            self.create_entry(i["name"], under_text=i["error"], side_text="!")

        if len(normal_item) > 0: self.create_heading("Successful Items")
        for i in normal_item:
            self.create_entry(i["name"], under_text=i.get('message', None))
        #if someone wanted to add email support for reciepts later, they could do it here
        #maybe post a request for a reciept to the server using the GTID in global state + the items in the transaction

#intercepts all events to see when activity occurs
#used to update the time since last action for the idle timer
class TimeoutKeyInterceptor(QObject):
    def __init__(self, controller):
        super().__init__()

        self.controller = controller

    #overrides the event filter to intercept all events
    def eventFilter(self, obj, event):
        self.controller.set_last_click()
        return QMainWindow.eventFilter(self, obj, event)



app = QApplication([])
window = MainWindow()


window.show()

#download global stylesheet
with open('main.qss') as f:
    app.setStyleSheet(f.read())

controller = ApplicationController(window)

tki = TimeoutKeyInterceptor(controller)
window.installEventFilter(tki)

window.stack.addWidget(StartScreen(controller))

app.exec()