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

import networkx as nx
import yaml
from path import path

from flask.ext.security import current_user
from thumbnail import Thumbnailer

ALBUM_YML = 'album.yml'

# list of supported image extension
# and their corresponding MIME type
PHOTO_SUPPORTED = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
}

# list of supported video extension
# and their corresponding MIME type
VIDEO_SUPPORTED = {
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.ogv': 'video/ogg',
}


class Library(nx.DiGraph):
    """Library

    Parameters
    ----------
    photo_dir : `path.path`
        Absolute path to library root directory
    """

    def __init__(self, photo_dir, thumb_dir, thumbnail=200, display=600):
        # initialize empty directed graph
        super(Library, self).__init__(root=path(photo_dir),)
        self.photo_dir = photo_dir
        self.thumb_dir = thumb_dir
        self.thumb_height = thumbnail
        self.display_height = display
        self.thumbnailer = Thumbnailer(
            self.photo_dir, self.thumb_dir, self.thumb_height)
        self.displayer = Thumbnailer(
            self.photo_dir, self.thumb_dir, self.display_height)
        # build the directory tree
        self._reset()

    @staticmethod
    def _load_yaml(directory):
        """Load `directory`/ALBUM_YML file

        Parameters
        ----------
        directory : `path.path`
            Directory where to look for ALBUM_YML file.

        Returns
        -------
        config : dict
            Content of ALBUM_YML file, as dictionary:
                'name':   album name (defaults to directory basename)
                'users':  set of users allowed to browse `directory`
                          (defaults to empty set)
                'groups': set of groups whose users are allowed to browse
                          `directory` (defaults to empty set)
        """

        config = {
            'name': directory.basename(),
            'users': set([]),
            'groups': set([]),
        }

        # `directory`/album.yml
        album_yml = path.joinpath(directory, ALBUM_YML)

        # load it if you can
        if album_yml.isfile():

            with open(album_yml, mode='r') as _:
                content = yaml.load(_)

                if 'name' in content:
                    config['name'] = content['name']

                if 'users' in content:
                    config['users'] = set(content['users'])

                if 'groups' in content:
                    config['groups'] = set(content['groups'])

        return config

    def _reset(self):
        """Reset library tree from root"""

        # empty tree
        self.remove_nodes_from(self)

        # root directory
        root = self.graph['root']

        # load root configuration
        config = self._load_yaml(root)

        # add root node (relative to root path)
        album = path('')
        self.add_node(
            album,
            name=config['name'],
            media=self._media(album),
            users=config['users'],
            groups=config['groups']
        )

        # traverse hierarchy (and build tree)
        self._traverse(path(''), config)

    def _supported(self, medium):
        """Check whether `medium` is supported

        Parameters
        ----------
        medium : `path.path`
            Absolute path to medium

        Returns
        -------
        supported : boolean
            True if medium is supported, False otherwise.
        """
        ext = medium.ext.lower()
        return ext in PHOTO_SUPPORTED or ext in VIDEO_SUPPORTED

    def _media(self, album):
        """Get list of supported media in `album`

        Parameters
        ----------
        album : `path.path`
            Album directory (relative to root)

        Returns
        -------
        supported_media : list
            list of supported media.
        """

        # obtain current directory absolute path
        root = self.graph['root']
        directory = path.joinpath(root, album)

        # loop on all files
        supported_media = []
        for m in directory.files():

            # add only supported ones
            if self._supported(m):
                medium = path.joinpath(album, m.basename())
                supported_media.append(medium)

        return supported_media

    def _traverse(self, album, config):
        """Traverse file hierarchy starting a root/album

        Parameters
        ----------
        album : `path.path`
            Current directory (relative to library root)
        config : dict
            Inherited configuration dictionary
        """

        # retrieve library root path
        root = self.graph['root']

        # obtain current directory absolute path
        directory = path.joinpath(root, album)

        # loop on all subdirectories
        for subdirectory in directory.dirs():

            # load subdirectory configuration
            subconfig = self._load_yaml(subdirectory)

            # users and groups allowed for subdirectory
            # but not yet allowed for upper directories
            new_users = subconfig['users'] - config['users']
            new_groups = subconfig['groups'] - config['groups']

            # make sure they are allowed to traverse parent directories
            # down to the current subdirectory
            self._back_propagate(album, new_users, new_groups)

            # inherit configuration dictionary from parent
            # and update it with subdirectory configuration
            subconfig['users'] = config['users'] | subconfig['users']
            subconfig['groups'] = config['groups'] | subconfig['groups']

            # create subdirectory album node
            subalbum = path.joinpath(album, subdirectory.basename())

            self.add_node(
                subalbum,
                name=subconfig['name'],
                # list of supported media
                media=self._media(subalbum),
                # users can see images in this sub-album
                users=subconfig['users'],
                # groups members can see images in this sub-album
                groups=subconfig['groups']
            )

            # connect parent directory with subdirectory
            self.add_edge(
                album,
                subalbum,
                # users can traverse this sub-album
                users=subconfig['users'],
                # groups members can traverse this sub-album
                groups=subconfig['groups']
            )

            # go one level deeper
            self._traverse(subalbum, subconfig)

    def _back_propagate(self, album, new_users, new_groups):
        """Back-propagate configuration to parent directories

        Parameters
        ----------
        album : `path.path`
            Current directory (relative to library root)
        new_users : set
            New users allowed to traverse down to album
        new_groups : set
            New groups allowed to traverse down to album
        """

        stop = True

        # (this loop is not a real loop as each album has at most one parent)
        for supalbum in self.predecessors(album):

            # users and groups allowed to traverse down to album
            users = self[supalbum][album]['users']
            groups = self[supalbum][album]['groups']

            # in case there really are new users
            if new_users - users:
                # allow them and set stop to False to continue back-propagation
                users = users | new_users
                self[supalbum][album]['users'] = users
                stop = False

            # same for groups
            if new_groups - groups:
                groups = groups | new_groups
                self[supalbum][album]['groups'] = groups
                stop = False

            # continue back-propagation if needed
            if not stop:
                self._back_propagate(supalbum, new_users, new_groups)

    def userIsAllowed(self, config):
        """Check whether current user is allowed according to `config`

        Parameters
        ----------
        config : dict

        Returns
        -------
        allowed : boolean
            True if current user is allowed according to `config`,
            False otherwise
        """

        if current_user.email in config['users'] or \
           current_user.has_role('admin'):
            return True

        # if groups and (set(groups) & config['groups']):
        #   return True

        return False

    def userCanTraverseAlbum(self, album):
        """Check whether current user can traverse `album`

        Parameters
        ----------
        album : `path.path`
            Album directory (relative to root)

        Returns
        -------
        traversable : boolean
            True if current user can traverse `album`, False otherwise
        """

        if album == '':
            return True

        supalbum = self.predecessors(album)[0]
        return self.userIsAllowed(self[supalbum][album])

    def getPathToAlbum(self, album):

        if not self.userCanTraverseAlbum(album):
            return None

        shortest_path = nx.shortest_path(self, source=path(''),
                                         target=path(album),
                                         weight=None)

        return [(p, p.basename()) for p in shortest_path[1:]]

    def getSiblings(self, album):
        parent = self.predecessors(album)[0]
        return sorted(self.successors(parent))

    def getAlbumSubAlbums(self, album):
        """Get list of traversable sub-albums

        Parameters
        ----------
        album : `path.path`
            Album directory (relative to root)

        Returns
        -------
        subalbums : list or None
            None if `user` cannot traverse `album`,
            list of traversable sub-albums if they can.
        """

        if not self.userCanTraverseAlbum(album):
            return None

        return sorted([
            subalbum for subalbum in self.successors(album)
            if self.userIsAllowed(self[album][subalbum])
        ])

    def userCanBrowseAlbum(self, album):
        """Check whether current user can browse `album`

        Parameters
        ----------
        album : `path.path`
            Album directory (relative to root)

        Returns
        -------
        traversable : boolean
            True if current user can browse `album`, False otherwise
        """
        if album == '':
            return True

        return self.userIsAllowed(self.node[album])

    def getAlbumMedia(self, album):
        """Get list of media in `album`

        Parameters
        ----------
        album : `path.path`
            Album directory (relative to root)

        Returns
        -------
        supported_media : list or None
            None if current user cannot browse `album`,
            list of supported media if they can.
        """

        if not self.userCanBrowseAlbum(album):
            return None

        return self.node[album]['media']

    def userCanGetMedium(self, medium):
        medium = path(medium)
        album = medium.dirname()
        return self.userCanBrowseAlbum(album)

    def getMediumMIMEType(self, medium):
        return 'image/jpeg'

    def getDisplay(self, medium):
        medium = path(medium)
        if self.userCanGetMedium(medium):
            return self.displayer(medium)

    def getDisplayMIMEType(self, medium):
        return 'image/jpeg'

    def getThumbnail(self, medium):
        medium = path(medium)
        if self.userCanGetMedium(medium):
            return self.thumbnailer(medium)

    def getThumbnailMIMEType(self, medium):
        return 'image/jpeg'

    # def getAbsolutePath(self, relative_path):
    #     """Get absolute path"""
    #     root = self.graph['root']
    #     return path.joinpath(root, relative_path)


def library_setup(app, original_dir, thumbnail_dir, thumbnail, display):

    library = Library(original_dir,
                      thumbnail_dir, thumbnail=thumbnail, display=display)

    app.config['library'] = library

    # inject `library` into the context of templates
    # http://flask.pocoo.org/docs/templating/#context-processors
    @app.context_processor
    def inject_library():
        return dict(library=library)

    return library

