#!/usr/bin/env python
# encoding: utf-8

#
# The MIT License (MIT)
#
# Copyright (c) 2013-2014 Hervé BREDIN (http://herve.niderb.fr/)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

"""

Usage:
    run [--debug] <config>

Arguments:
    <config>  path to configuration file.

Options:
    --debug   enable debug mode.

"""

import yaml
from path import path
from docopt import docopt

from flask import render_template, redirect, url_for, send_file
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required
from flask.ext.security.forms import LoginForm
from flask_mail import Mail

from phlask import app
from phlask.library import Library
from phlask.library import USER_ROLE_NAME, USER_ROLE_DESCRIPTION, \
    ADMIN_ROLE_NAME, ADMIN_ROLE_DESCRIPTION

if __name__ == '__main__':

    ARGUMENTS = docopt(__doc__)

    with open(ARGUMENTS['<config>'], mode='r') as _:
        CONFIG = yaml.load(_)

    app.secret_key = CONFIG['secret_key']
    app.debug = ARGUMENTS['--debug']

    app.config['SECURITY_CONFIRMABLE'] = True
    app.config['SECURITY_REGISTERABLE'] = True
    app.config['SECURITY_RECOVERABLE'] = True
    app.config['SECURITY_TRACKABLE'] = False
    app.config['SECURITY_PASSWORDLESS'] = False
    app.config['SECURITY_CHANGEABLE'] = True
    app.config['SECURITY_DEFAULT_REMEMBER_ME'] = False
    app.config['SECURITY_LOGIN_WITHOUT_CONFIRMATION'] = True
    # app.config['SECURITY_URL_PREFIX'] = None
    # app.config['SECURITY_FLASH_MESSAGES'] = True
    # app.config['SECURITY_PASSWORD_HASH'] = 'plaintext'
    # app.config['SECURITY_PASSWORD_SALT'] = None
    # app.config['SECURITY_LOGIN_URL'] = '/login'
    # app.config['SECURITY_LOGOUT_URL'] = '/logout'
    # app.config['SECURITY_REGISTER_URL'] = '/register'
    # app.config['SECURITY_RESET_URL'] = '/reset'
    # app.config['SECURITY_CHANGE_URL'] = '/change'
    # app.config['SECURITY_CONFIRM_URL'] = '/confirm'
    # app.config['SECURITY_POST_LOGIN_VIEW'] = '/'
    # app.config['SECURITY_POST_LOGOUT_VIEW'] = '/'
    # app.config['SECURITY_CONFIRM_ERROR_VIEW'] = None
    # app.config['SECURITY_POST_REGISTER_VIEW'] = None
    # app.config['SECURITY_POST_CONFIRM_VIEW'] = None
    # app.config['SECURITY_POST_RESET_VIEW'] = None
    # app.config['SECURITY_POST_CHANGE_VIEW'] = None
    # app.config['SECURITY_UNAUTHORIZED_VIEW'] = None

    # ~~ MAIL ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    if 'mail' in CONFIG:

        app.config['MAIL_SERVER'] = CONFIG['mail']['server']
        app.config['MAIL_PORT'] = CONFIG['mail']['port']
        app.config['MAIL_USE_SSL'] = CONFIG['mail']['ssl']
        app.config['MAIL_USERNAME'] = CONFIG['mail']['username']
        app.config['MAIL_PASSWORD'] = CONFIG['mail']['password']

        app.config['SECURITY_EMAIL_SENDER'] = CONFIG['mail']['sender']
        app.config['SECURITY_SEND_REGISTER_EMAIL'] = True
        app.config['SECURITY_SEND_PASSWORD_CHANGE_EMAIL'] = True
        app.config['SECURITY_SEND_PASSWORD_RESET_NOTICE_EMAIL'] = True

        mail = Mail(app)

    # ~~ USER MANAGEMENT~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    database = CONFIG['phlask']['database']
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + database

    db = SQLAlchemy(app)

    roles_users = db.Table(
        'roles_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
        db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))

    class Role(db.Model, RoleMixin):
        id = db.Column(db.Integer(), primary_key=True)
        name = db.Column(db.String(80), unique=True)
        description = db.Column(db.String(255))

    class User(db.Model, UserMixin):
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(255), unique=True)
        password = db.Column(db.String(255))
        active = db.Column(db.Boolean())
        confirmed_at = db.Column(db.DateTime())
        roles = db.relationship(
            'Role',
            secondary=roles_users,
            backref=db.backref('users', lazy='dynamic')
        )

    # Setup Flask-Security
    datastore = SQLAlchemyUserDatastore(db, User, Role)

    security = Security(app, datastore)

    @app.before_first_request
    def create_root_user():

        db.create_all()

        # create 'admin' role if it does not exist
        admin_role = datastore.find_or_create_role(
            name=ADMIN_ROLE_NAME, description=ADMIN_ROLE_DESCRIPTION)

        # create 'user' role if it does not exist
        datastore.find_or_create_role(
            name=USER_ROLE_NAME, description=USER_ROLE_DESCRIPTION)

        # create 'admin' user (with 'admin' role) if it does not exist
        admin = datastore.get_user('root')
        if admin:
            # update password
            admin.password = CONFIG['phlask']['root_password']
        else:
            admin = datastore.create_user(
                email='root', password=CONFIG['phlask']['root_password'])
            datastore.add_role_to_user(admin, admin_role)

        db.session.commit()

    app.config['library'] = Library(
        CONFIG['phlask']['original_dir'],
        CONFIG['phlask']['thumbnail_dir'],
        thumbnail=int(CONFIG['phlask']['thumbnail_size']),
        display=int(CONFIG['phlask']['display_size']))

    # inject `library` into the context of templates
    # http://flask.pocoo.org/docs/templating/#context-processors
    @app.context_processor
    def inject_library():
        return dict(library=app.config['library'])

    @app.context_processor
    def inject_login_user_form():
        return dict(login_user_form=LoginForm())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ALBUMS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @app.route('/album/')
    @app.route('/album/<path:album>')
    @login_required
    def get_album(album=''):
        return render_template(
            'album.html', album=path(album),
            thumbnail_height=int(CONFIG['phlask']['thumbnail_size']),
            display_height=int(CONFIG['phlask']['display_size']))

    # redirect / to /album
    @app.route('/')
    def root():
        return redirect(url_for('get_album', album=''))

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # MEDIUMS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @app.route('/thumbnail/<path:medium>')
    @login_required
    def get_thumbnail(medium=None):
        return send_file(
            app.config['library'].getThumbnail(medium),
            mimetype=app.config['library'].getThumbnailMIMEType(medium)
        )

    @app.route('/display/<path:medium>')
    @login_required
    def get_display(medium=None):
        return send_file(
            app.config['library'].getDisplay(medium),
            mimetype=app.config['library'].getDisplayMIMEType(medium)
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ADMIN
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @app.route('/admin/reload')
    @login_required
    def reload():
        app.config['library'] = Library(
            CONFIG['phlask']['original_dir'],
            CONFIG['phlask']['thumbnail_dir'],
            thumbnail=CONFIG['phlask']['thumbnail_size'],
            display=CONFIG['phlask']['display_size'])
        return redirect(url_for('get_album', album=''))

    app.run()
