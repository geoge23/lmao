from flask import Blueprint, render_template, request, Response, jsonify, Markup, request, redirect, url_for
from models import Item, Image, User, Checkout, ApiKey
from peewee import Column, DoesNotExist
from flask_admin import Admin, AdminIndexView, expose, BaseView
from flask_admin.form import BaseForm
from wtforms import StringField
from flask_admin.contrib.peewee import ModelView
from flask_admin.model.form import InlineFormAdmin
from functools import partial
import base64

class AuthController():
    def is_accessible(self):
        try:
            api_key = request.cookies.get('api_key')
            ApiKey.select().where(ApiKey.code == api_key).dicts().get()
            return True
        except Exception as e:
            print(e)
            return False

    def inaccessible_callback(self, name, **kwargs):
        print(name)
        return redirect(url_for('loginview.index'))

class HomeView(AuthController, AdminIndexView):
    @expose('/')
    def index(self):
        return self.render('home.html')

class LoginView(AuthController, BaseView):
    @expose('/')
    def index(self):
        return self.render('login.html')

    def is_accessible(self):
        return True

    def is_visible(self):
        return not super().is_accessible()

class ItemAdmin(AuthController, ModelView):

    column_searchable_list = (Item.name, Item.description, Item.barcode)

    column_formatters = {
        'image': lambda v, c, m, p: Markup('<img src="{}" style="width:100px;height:100px">'.format("/image/{}".format(m.image))) if m.image else "None Attached"
    }

    form_overrides = {
        'barcode': StringField,
        'name': StringField,
        'image': partial(StringField, name="Image ID"),
    }

    create_template = "item_create.html"

    can_view_details = True

    @expose('/new/', methods=('GET', 'POST'))
    def create_view(self):
         self._template_args['api_key'] = request.cookies.get('api_key')
         return super(ItemAdmin, self).create_view()

class CheckoutAdmin(AuthController, ModelView):
    form_ajax_refs = {
        'user_id': {
            'fields': (User.name, User.gtid)
        },
        'item_id': {
            'fields': (Item.name, Item.barcode)
        }
    }

    column_default_sort = ('start_date', True)

    def get_column_names(self, only_columns, excluded_columns):
        return [('start_date', 'Start Date'), ('return_date', 'Return Date'), ('item_id.name', 'Item Name'), ('item_id.barcode', 'Item Barcode'), ('user_id.name', 'User Name'), ('user_id.gtid', 'User GTID')]

    def get_query(self):
        return self.model.select().join(Item)


    can_view_details=True
    can_create=False

class UserAdmin(AuthController, ModelView):
    column_searchable_list = (User.name, User.gtid, User.email)

class ApiAdmin(AuthController, ModelView):
    pass

class ImageAdmin(AuthController, ModelView):

    column_formatters = {
        'image': lambda v, c, m, p: Markup('<img src="{}" style="width:100px;height:100px">'.format("/image/{}".format(m.id))) if m.image else "None Attached"
    }

    can_edit = False
    can_view_details = True
    create_template = "image_create.html"

    @expose('/new/', methods=('GET', 'POST'))
    def create_view(self):
         self._template_args['api_key'] = request.cookies.get('api_key')
         return super(ImageAdmin, self).create_view()

admin = Admin(name="LMAO", template_mode="bootstrap3", index_view=HomeView())

admin.add_view(ItemAdmin(Item))
admin.add_view(ImageAdmin(Image))
admin.add_view(UserAdmin(User))
admin.add_view(ApiAdmin(ApiKey))
admin.add_view(LoginView(name="Login"))
admin.add_view(CheckoutAdmin(Checkout))