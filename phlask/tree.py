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

import logging
logging.basicConfig(level=logging.DEBUG)
import networkx as nx
import yaml
from path import path

ALBUM_YML = 'album.yml'
SUPPORTED = {
	'JPEG': ['jpg', 'jpeg', 'JPG', 'JPEG'], 
}

class Library(nx.DiGraph):
	"""Library

	Parameters
	----------
	root : `path.path`
		Absolute path to library root directory
	"""

	def __init__(self, root):
		# initialize empty directed graph
		super(Library, self).__init__(root=path(root))
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
		return True

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
				users = subconfig['users'],
				# groups members can see images in this sub-album
				groups = subconfig['groups']
			)

			# connect parent directory with subdirectory
			self.add_edge(
				album, 
				subalbum,
				# users can traverse this sub-album
				users = subconfig['users'],
				# groups members can traverse this sub-album
				groups = subconfig['groups']
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


	def is_allowed(self, config, user, groups=None):
		"""Check whether `user` is allowed according to `config`

		Parameters
		----------
		config : dict
		user : str
		groups : iterable, optional
			Groups `user` belongs to

		Returns
		-------
		allowed : boolean
			True if `user` is allowed according to `config`, False otherwise
		"""
		
		if user in config['users']:
			return True

		if groups and (set(groups) & config['groups']):
			return True 
		
		return False

	def is_traversable(self, album, user, groups=None):
		"""Check whether `user` can traverse `album`

		Parameters
		----------
		album : `path.path`
			Album directory (relative to root)
		user : str
		groups : iterable, optional
			Groups `user` belongs to

		Returns
		-------
		traversable : boolean
			True if `user` can traverse `album`, False otherwise
		"""

		if album == '':
			return True

		supalbum = self.predecessors(album)[0]
		return self.is_allowed(self[supalbum][album], user, groups=groups)

	def sub_albums(self, album, user, groups=None):
		"""Get list of traversable sub-albums

		Parameters
		----------
		album : `path.path`
			Album directory (relative to root)
		user : str
		groups : iterable, optional
			Groups `user` belongs to

		Returns
		------- 
		subalbums : list or None
			None if `user` cannot traverse `album`, 
			list of traversable sub-albums if they can.
		"""

		if not self.is_traversable(album, user, groups=groups):
			return None

		return [
			subalbum for subalbum in self.successors(album)
			if self.is_allowed(self[album][subalbum], user, groups=groups)
		]

	def is_browsable(self, album, user, groups=None):
		"""Check whether `user` can browse `album`

		Parameters
		----------
		album : `path.path`
			Album directory (relative to root)
		user : str
		groups : iterable, optional
			Groups `user` belongs to

		Returns
		-------
		traversable : boolean
			True if `user` can browse `album`, False otherwise
		"""
		if album == '':
			return True

		return self.is_allowed(self.node[album], user, groups=groups)

	def media(self, album, user, groups=None):
		"""Get list of media in `album` 

		Parameters
		----------
		album : `path.path`
			Album directory (relative to root)
		user : str
		groups : iterable, optional
			Groups `user` belongs to

		Returns
		------- 
		supported_media : list or None
			None if `user` cannot browse `album`, 
			list of supported media if they can.
		"""

		if not self.is_browsable(album, user, groups=groups):
			return None

		return self.node[album]['media']
