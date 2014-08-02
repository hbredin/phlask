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
from flask.ext.security import login_required
from flask.ext.security.forms import LoginForm

from utils.library import library_setup
from utils.security import security_setup
from utils.mail import mail_setup

from flask import Flask
app = Flask(__name__)

if __name__ == '__main__':

    ARGUMENTS = docopt(__doc__)

    with open(ARGUMENTS['<config>'], mode='r') as _:
        CONFIG = yaml.load(_)

    app.secret_key = CONFIG['phlask']['secret_key']
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

    pathToDatabase = path.joinpath(CONFIG['phlask']['working_dir'], 'phlsk.db')
    security = security_setup(app, pathToDatabase,
                              CONFIG['phlask']['root_password'])

    _config = CONFIG['mail']
    mail = mail_setup(app,
                      server=_config['server'], port=_config['port'],
                      use_ssl=_config['ssl'], username=_config['username'],
                      password=_config['password'], sender=_config['sender'])

    library = library_setup(
        app,
        CONFIG['phlask']['original_dir'],
        path.joinpath(CONFIG['phlask']['working_dir'], 'thumb'),
        thumbnail=int(CONFIG['phlask']['thumbnail_size']),
        display=int(CONFIG['phlask']['display_size']))

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
        library_setup(
            app,
            CONFIG['phlask']['original_dir'],
            path.joinpath(CONFIG['phlask']['working_dir'], 'thumb'),
            thumbnail=int(CONFIG['phlask']['thumbnail_size']),
            display=int(CONFIG['phlask']['display_size']))
        return redirect(url_for('get_album', album=''))

    app.run()
