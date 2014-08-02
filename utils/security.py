#!/usr/bin/env python
# encoding: utf-8

#
# The MIT License (MIT)
#
# Copyright (c) 2014 Hervé BREDIN (http://herve.niderb.fr/)
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

from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.security import Security
from flask.ext.security import SQLAlchemyUserDatastore, UserMixin, RoleMixin


def security_setup(app, pathToDatabase, rootPassword):

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + pathToDatabase

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
        admin_role = datastore.find_or_create_role(name='admin')

        # create 'user' role if it does not exist
        datastore.find_or_create_role(name='user')

        # create 'admin' user (with 'admin' role) if it does not exist
        admin = datastore.get_user('root')
        if admin:
            # update password
            admin.password = rootPassword
        else:
            admin = datastore.create_user(
                email='root', password=rootPassword)
            datastore.add_role_to_user(admin, admin_role)

        db.session.commit()

    return security
