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

from phlask import app
from docopt import docopt
from phlask.tree import Tree
from path import path
import yaml

from flask import render_template
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required


if __name__ == '__main__':

    ARGUMENTS = docopt(__doc__)

    with open(ARGUMENTS['<config>'], mode='r') as _:
        config = yaml.load(_)

    app.secret_key = config['secret_key']
    app.debug = config['debug']


    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'

    # Create database connection object
    db = SQLAlchemy(app)

    # Define models
    roles_users = db.Table('roles_users',
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
            backref=db.backref('users', lazy='dynamic'))

    # Setup Flask-Security
    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    security = Security(app, user_datastore)

    # Create a user to test with
    @app.before_first_request
    def create_user():
        db.create_all()
        user_datastore.create_user(email='herve.bredin@gmail.com', password='password')
        db.session.commit()

    app.config['photo_dir'] = path(config['photo_dir'])
    app.config['thumb_dir'] = path(config['thumb_dir'])

    app.tree = Tree(app.config['photo_dir'])

    # Views
    @app.route('/')
    @login_required
    def home():
        return render_template('index.html')

    

    app.run()
