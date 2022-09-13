# Lab Management Asset Organizer

Lab Management Asset Organizer, or LMAO for short, is an inventory management system for the EOSL labs. It runs on a Raspberry Pi with an accompanying server running wherever space is available. The system is developed by 2022 STEM@GTRI interns George Parks and Mallika Kulkarni. 

## First-time setup

### Raspberry Pi

To configure the Raspberry Pi, you'll need to perform a few steps. LMAO supports an infinte number of Pis connected to the primary server, so feel free to set up several to increase the reach of the system. This software is designed to run on the Lite version of Raspbian

0) Setup SSH

Make sure there is SSH access to the Raspberry Pi for debugging and maintenence purposes. It is exceedingly inconvenient to force-restart with the display locked down by the LMAO interface.


1) Install linux packages

You'll also need the following packages installed
```sh
sudo apt install python3-pyqt5 xorg openbox lightdm git feh python3-pip
```

2) Install PIP packages

You'll need to install the following packages:
```python
pyserial==3.5
requests==2.28.0
```

3) Configure Autostart

Add the following line to `$HOME/.config/openbox/autostart`, and make sure this file is executable (`chmod +x`)
```sh
$HOME/app/run.sh &
```
Make sure your Pi is configured to automatically login to the user account you created via GUI. You can do this by running `sudo raspi-config` and changing the `Auto Login` option to `Desktop Autologin` under `System Options`.

> ❗ If you're running into problems, you can see the logs by replacing the contents of `$HOME/.config/openbox/autostart` with the following:
> ```sh
> $HOME/app/run.sh >$HOME/lmao_log 2>&1 &
> ```
> You can then run the window manager with `startx` and read the errors using `cat ~/lmao_log`

4) Download code bundle

Clone the git repository into the `$HOME/app` directory.
```sh
git clone https://github.com/geoge23/lmao.git $HOME/app
```

1) Configure the app

Create a new file called `evars.sh` in the `$HOME/app` directory. Export any relevant environment variables you need to run the app. For instance:
```sh
export RFID_SERIAL_PORT=/dev/serial/by-id/usb-RFIDeas_USB_Serial-if00
export SCANNER_SERIAL_PORT=/dev/serial/by-id/usb-SuperLead_2208_CF221B1B0171-if00
export URL=http://10.0.0.5:5000
export KEY=(API KEY)
```
More environment variables can be seen in the `example.env` file

6) Reboot your Pi

Everything should be configured, just reboot the Pi and the service should begin working automatically. The process may take up to two minutes to initialize, during which there may be no display output.

> ℹ Any exit code other than SIGTERM will cause the process to be restarted. If you need to kill the LMAO process, open an SSH session and run `pkill python`. This will terminate the process and return you to Openbox, where you can right click to get a menu of options. If you want to return to LMAO, just spawn a terminal and run `~/app/run.sh`.

> ℹ To improve the user experience for those using the Pi, run the script at `vanity/graphics-setup.sh` to set up the desktop environment UI. This adds launch screen splashes and configures desktop backgrounds. Make sure you're in the `$HOME/app` directory before running this script. 

### Server

These instructions are intended for a Windows server. 
1) Install Python 

Download Python from the Microsoft Store or [the website](https://www.python.org/downloads/). Make sure that Python is added to PATH. Then, install the following packages. 
```python
Flask==2.1.2
peewee==3.14.10
psycopg2==2.9.3
requests==2.28.0
flask-admin==1.6.0
wtf-peewee==3.0.4
waitress=2.1.2
```

2) Install Postgres

Download and install PostgreSQL from [the website](https://www.postgresql.org/download/). Go through the wizard and make note of the user you create, since you will need this later to authenticate the server with the database

3) Download code bundle

Clone the git repository onto your system
```sh
git clone https://github.com/geoge23/lmao.git
```

4) Configure environment variables

Open the `run.bat` file located in `./server` using a text editor. Change the `POSTGRES_USER` and `POSTGRES_PASSWORD` variables to match the user and password you created in the previous step. Make note of the absolute path to this directory, as you will need it next.

5) Configure the task for Windows Scheduler

Open the `lmao-server-task.xml` file located in `./server` using a text editor. Locate the `<Actions>` section and set the relevant tags based on the absolute path from the last step. The section should look something like this.

```xml
<Actions Context="Author">
 <Exec>
   <Command>C:\Users\[YOUR USER]\Documents\inventory\server\env_run.bat</Command>
   <WorkingDirectory>C:\Users\[YOUR USER]\Documents\inventory\server</WorkingDirectory>
 </Exec>
</Actions>
```

6) Add the task

Press `WIN + R` to open the Run dialog. Type `taskschd.msc` into the box and press `ENTER`. This will open the Scheduler. In the top left, press `Action > Import Task`. Select the `lmao-server-task.xml` file you just created. Press `OK`. Authenticate using an admin account in the dialog that appears. The task should now be added to the Scheduler.

7) Start the server

Find `lmao-server` in the list of scheduled jobs in the Scheduler. Right-click on the job and select `Run`. This starts the server at :80.

8) Get your API key

When the server starts for the first time, an API key will be written to `./server/key`. This is the key you will need to use to authenticate with the server for the first time. When you navigate to the admin panel for the first time, you will see a login window. Paste your API key into the `api_key` box and click `Login`.

> ❗ The API key will only generate if there are no already existing keys in the database. Feel free to delete the `key` file when you're done with it. If you've lost access to your keys, you will need to manually access the database and add an entry to the api_keys table.

> ℹ If you want to change the port that the server listens on (or add more arguments to the WSGI server command), edit the `run.bat` file in `./server`.

## Admin Panel
The LMAO Admin panel is always accessable at `/admin`
### Creating API keys
To connect clients to the API, they must first create an API key. This is done by going to the admin panel and clicking on the `API Keys` tab. Press create, and an API key will be generated. Then press Save to activate it. The key will be displayed in the `API Key` field. For security purposes, one key should be used for one client, and these keys should not be shared with anyone else. Keys can be revoked by deleting them in the admin panel.
### Adding users
While it is possible to add users from this panel if you know their unique GT badge ID, it is recommended to add this data via the onboarding screen when scanning an unknown ID badge from a Pi terminal.
> ℹ The GTID referenced in the database differs from Georgia Tech's actual GTIDs, since the tapcards do not hold GTIDs. They have UUIDs, which are used to authenticate with the system. Do not use the GTID in the database, but instead use the UUID from the card.
### Adding items
To add items, navigate to the admin panel and click on the `Items` tab. Fill out the relevant fields and click `Add Item`. The item will be added to the database. If you want to use an already existing image for your item, you can include an image ID from the `Images` tab in the `Image ID` field.
> ℹ Images will be automatically resized to 400x400 pixels on upload. Please use JPG or PNG files for best results

### Viewing checkouts
The `Checkouts` tab is used to view all checkouts. These are automatically sorted by date, with the most recent checkouts appearing first. If necessary, you can edit checkout information by pressing the `Edit` icon next to each entry. This allows you to change the date of the checkout, or the item that was checked out. Items not yet returned will have the `Return Date` field blank in the UI. Sorting by `Return Date` will show all items that have not been returned.

> ❗ The Item and User ID fields in the `Edit` window will only show an ID. To associate with an item or user, start typing its barcode or name and a relevant ID will appear. 

## Things to know
- Any user can check out an item. Furthermore, any user can return an item, regardless of who checked it out.
- Users will automatically be logged out of the Pi after 3 minutes of inactivity.
- If the UI becomes stuck on the Tap ID screen, it likely means that the Pi client cannot connect to the server. Ensure that the server URL is correct and that the server is accessible from the Pi client.
