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

from PIL import Image
from path import path


EXIF_ORIENTATION_KEY = 274

ROTATE_BY = {1: 0, 8: 90, 3: 180, 6: 270}
IS_LANDSCAPE = {1: True, 3: True, 8: False, 6: False}


class Thumbnailer(object):

    def __init__(self, original_dir, thumbnail_dir, height, extension='.jpg'):
        super(Thumbnailer, self).__init__()
        self.original_dir = original_dir
        self.thumbnail_dir = thumbnail_dir
        self.height = height
        self.extension = extension

    def _absolute_path_to_original(self, relative_path):
        return path.joinpath(self.original_dir, relative_path)

    def _absolute_path_to_thumbnail(self, relative_path):

        # absolute path to thumbnail
        thumbnail_path = path.joinpath(
            self.thumbnail_dir, '{height:d}'.format(height=self.height),
            relative_path)

        # change file extension to .jpg
        allButExtension, extension = thumbnail_path.splitext()
        return allButExtension + self.extension

    def _generate_thumbnail(self, original_path, thumbnail_path):

        # load original image
        original = Image.open(original_path)

        # remember how many degrees it should be rotated by
        exif = original._getexif()
        orientation = exif.get(EXIF_ORIENTATION_KEY, None)
        angle = ROTATE_BY.get(orientation, 0)

        # in-place thumbnail
        width, height = original.size
        if IS_LANDSCAPE.get(orientation, True):
            ratio = 1. * self.height / height
            size = (int(ratio * width), self.height)
        else:
            ratio = 1. * self.height / width
            size = (self.height, int(ratio * height))
        original.thumbnail(size, Image.ANTIALIAS)

        # rotate the thumbnail
        rotated = original.rotate(angle)

        # save thumbnail
        thumbnail_path.parent.makedirs_p()
        rotated.save(thumbnail_path)

    def __call__(self, relative_path):

        # get absolute path of original image and last modified time
        original_path = self._absolute_path_to_original(relative_path)
        original_mtime = original_path.mtime

        # get absolute path to thumbnail image
        thumbnail_path = self._absolute_path_to_thumbnail(relative_path)

        # if thumbnail exists and is recent enough, return its absolute path
        if thumbnail_path.isfile() and thumbnail_path.mtime > original_mtime:
            return thumbnail_path

        # otherwise, generate it and return its absolute path
        self._generate_thumbnail(original_path, thumbnail_path)
        return thumbnail_path
