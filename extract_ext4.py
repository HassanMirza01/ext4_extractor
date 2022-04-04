#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import ext4


class ExtractExt4():
  def __init__(self):
    self.image_name = os.path.realpath(sys.argv[1])
    self.file_name = self.__file_name(os.path.basename(self.image_name))
    self.out_dir = os.path.realpath(sys.argv[2])
    self.num_files = 0
    self.num_dirs = 0
    self.num_links = 0

  def __file_name(self, file_path):
    name = os.path.basename(file_path).split('.')[0]
    return name

  def extract_ext4(self):

    def scan_dir(root_inode, root_path=""):
      for entry_name, entry_inode_idx, entry_type in root_inode.open_dir():
        # exclude '.', '..'
        if entry_name in ['.', '..', 'lost+found']:
          continue

        entry_inode = root_inode.volume.get_inode(entry_inode_idx, entry_type)
        entry_inode_path = root_path + '/' + entry_name

        if entry_inode.is_dir:
          self.num_dirs += 1
          dir_target = self.out_dir + \
            entry_inode_path.replace('"permissions"', 'permissions')

          if not os.path.isdir(dir_target):
            os.makedirs(dir_target)

          scan_dir(entry_inode, entry_inode_path)  # loop inside the directory

        elif entry_inode.is_file:
          self.num_files += 1
          # extract files
          raw = entry_inode.open_read().read()

          file_target = os.path.join(self.out_dir + entry_inode_path)

          if os.path.isfile(file_target):
            os.remove(file_target)

          # write to new file
          with open(file_target, 'wb') as out:
            out.write(raw)

        elif entry_inode.is_symlink:
          self.num_links += 1
          link_target = entry_inode.open_read().read().decode("utf-8")
          target = self.out_dir + entry_inode_path

          # check if file exist and remove it
          if os.path.islink(target) or os.path.isfile(target):
            os.remove(target)

          # make link
          os.symlink(link_target, target)

    # open image
    with open(self.image_name, 'rb') as file:
      root = ext4.Volume(file).root
      scan_dir(root)

    print(f'{self.num_dirs} DIR {self.num_files} FILE {self.num_links} LINKS')


if __name__ == '__main__':
  if sys.argv.__len__() < 3:
    print(f'USAGE: {sys.argv[0]} image_path out_path')
  else:
    print(
      f':: Extract {ExtractExt4().file_name}.img...',
      f':: Image path -> {ExtractExt4().image_name}',
      f':: Info dir   -> {ExtractExt4().out_dir}',
      sep='\n', end='\n\n')
    ExtractExt4().extract_ext4()
