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

from phlask import app
from phlask.library import Library
from phlask.library import USER_ROLE_NAME, USER_ROLE_DESCRIPTION, \
    ADMIN_ROLE_NAME, ADMIN_ROLE_DESCRIPTION, ADMIN_USER

if __name__ == '__main__':

    ARGUMENTS = docopt(__doc__)

    with open(ARGUMENTS['<config>'], mode='r') as _:
        CONFIG = yaml.load(_)

    app.secret_key = CONFIG['secret_key']
    app.debug = CONFIG['debug']

    # Flask-Security configuration
    # app.config['SECURITY_BLUEPRINT_NAME'] = 'security'
    # app.config['SECURITY_URL_PREFIX'] = '/api'

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + CONFIG['database']

    # Create database connection object
    db = SQLAlchemy(app)

    # Define models
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
    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    security = Security(app, user_datastore)

    @app.before_first_request
    def create_root_user():

        db.create_all()

        # create 'admin' role if it does not exist
        admin_role = user_datastore.find_or_create_role(
            name=ADMIN_ROLE_NAME, description=ADMIN_ROLE_DESCRIPTION)

        # create 'user' role if it does not exist
        user_datastore.find_or_create_role(
            name=USER_ROLE_NAME, description=USER_ROLE_DESCRIPTION)

        # create 'admin' user (with 'admin' role) if it does not exist
        admin = user_datastore.get_user(ADMIN_USER)
        if admin:
            # update password
            admin.password = CONFIG['password']
        else:
            admin = user_datastore.create_user(
                email=ADMIN_USER, password=CONFIG['password'])
            user_datastore.add_role_to_user(admin, admin_role)

        db.session.commit()

    photo_dir = path(CONFIG['photo_dir'])
    thumb_dir = path(CONFIG['thumb_dir'])
    thumbnail = int(CONFIG['thumbnail'])
    app.config['library'] = Library(
        photo_dir, thumb_dir, thumbnail=thumbnail)

    # from route.api import api
    # app.register_blueprint(api, url_prefix='/api')

    # inject `library` into the context of templates
    # http://flask.pocoo.org/docs/templating/#context-processors
    @app.context_processor
    def inject_library():
        return dict(library=app.config['library'])

    @app.route('/')
    @login_required
    def root():
        return redirect(url_for('get_album', album=''))

    @app.route('/album/')
    @app.route('/album/<path:album>')
    @login_required
    def get_album(album=''):
        return render_template('album.html', album=path(album))

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

    # @app.route('/medium/<path:medium>')
    # @login_required
    # def get_medium(medium=None):
    #     return send_file(
    #         app.config['library'].absolute_path(medium)
    #     )

    app.run()
