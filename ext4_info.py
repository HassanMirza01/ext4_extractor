#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import ext4


class ReadExt4():
  def __init__(self):
    self.image_name = os.path.realpath(sys.argv[1])
    self.out_dir = os.path.realpath(sys.argv[2])
    self.fs_context = []
    self.fs_config = []
    self.fetures = []
    self.file_name = self.__file_name(os.path.basename(self.image_name))
    self.fs_context_file = os.path.join(
      self.out_dir, self.file_name + "_file_contexts.txt")
    self.fs_config_file = os.path.join(
      self.out_dir, self.file_name + '_file_config.txt')
    self.file_features = os.path.join(
      self.out_dir, self.file_name + '_file_features.txt')
    self.num_files = 0
    self.num_dirs = 0
    self.num_links = 0

  def __file_name(self, file_path):
    name = os.path.basename(file_path).split('.')[0]
    return name

  def __get_octal_perm(self, arg):
    if len(arg) < 9 or len(arg) > 10:
      return
    if len(arg) > 8:
      arg = arg[1:]
    oor, ow, ox, gr, gw, gx, wr, ww, wx = list(arg)
    o, g, w, s = 0, 0, 0, 0
    if oor == 'r':
      o += 4
    if ow == 'w':
      o += 2
    if ox == 'x':
      o += 1
    if ox == 'S':
      s += 4
    if ox == 's':
      s += 4
      o += 1
    if gr == 'r':
      g += 4
    if gw == 'w':
      g += 2
    if gx == 'x':
      g += 1
    if gx == 'S':
      s += 2
    if gx == 's':
      s += 2
      g += 1
    if wr == 'r':
      w += 4
    if ww == 'w':
      w += 2
    if wx == 'x':
      w += 1
    if wx == 'T':
      s += 1
    if wx == 't':
      s += 1
      w += 1
    return str(s) + str(o) + str(g) + str(w)

  def __appendf(self, msg, out_file):
    with open(out_file, 'w') as file:
      file.write('{}\n'.format(msg))

  def __write_context(self):
    """
    write context from fs_context list to file
    """
    if self.file_name == 'vendor' or self.file_name == 'odm':
      self.fs_context.append('/ u:object_r:vendor_file:s0')
      self.fs_context.append(
        f'/{self.file_name}(/.*)? u:object_r:vendor_file:s0')
    
    else:
      self.fs_context.append('/ u:object_r:system_file:s0')
      self.fs_context.append(
        f'/{self.file_name}(/.*)? u:object_r:system_file:s0')

    if self.file_name == 'system':
      self.fs_context.append(f'/lost+found        u:object_r:rootfs:s0')
    else:
      self.fs_context.append(
        f'/{self.file_name}/lost+found        u:object_r:rootfs:s0')

    # replace . with \. in list
    self.fs_context = [ele.replace('.', r'\.') for ele in self.fs_context]
    # replace + with \+ in list
    self.fs_context = [ele.replace('+', r'\+') for ele in self.fs_context]
    self.fs_context.sort()
    # write contexts to file
    self.__appendf('\n'.join(self.fs_context), self.fs_context_file)

  def __write_config(self):
    """
    write config from fs_config list to file
    """
    if self.file_name == 'vendor':
      self.fs_config.append('/ 0 2000 0755')
      self.fs_config.append(f'{self.file_name} 0 2000 0755')
    
    else:
      self.fs_config.append('/ 0 0 0755')
      self.fs_config.append(f'{self.file_name} 0 0 0755')

    self.fs_config.sort()
    # write config list to file
    self.__appendf('\n'.join(self.fs_config), self.fs_config_file)

  def __write_fetures(self):
    if os.name == 'posix':
      cmd = ['tune2fs', '-l', self.image_name]
      p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True)
      output, _ = p.communicate()

      with open(self.file_features, 'w') as file:
        for line in output:
          file.write(line)
        file.write('Partition size: {}'.format(
          os.stat(self.image_name).st_size))

    else:
      with open(self.image_name, 'rb') as file:
        self.fetures.append('Filesystem volume name:'+' '*4 +
                            ext4.Volume(file).superblock.s_volume_name.decode())
        self.fetures.append('Last mounted on:'+' '*11 +
                            ext4.Volume(file).superblock.s_last_mounted.decode())
        self.fetures.append('Filesystem UUID:'+' '*11 +
                            ext4.Volume(file).uuid.lower())
        self.fetures.append('Filesystem magic number:   ' +
                            hex(ext4.Volume(file).superblock.s_magic))
        self.fetures.append('Inode count:'+' '*15 +
                            str(ext4.Volume(file).superblock.s_inodes_count))
        self.fetures.append('Block size:'+' '*16 +
                            str(ext4.Volume(file).block_size))
        self.fetures.append('Inode size:'+' '*16 +
                            str(ext4.Volume(file).superblock.s_inode_size))
        self.fetures.append('Inodes per group:'+' '*10 +
                            str(ext4.Volume(file).superblock.s_inodes_per_group))
        # write to file
        self.__appendf('\n'.join(self.fetures), self.file_features)

  def read_ext4(self):
    def scan_dir(root_inode, root_path=""):
      for entry_name, entry_inode_idx, entry_type in root_inode.open_dir():
        # exclude '.', '..'
        if entry_name in ['.', '..', 'lost+found']:
          continue

        entry_inode = root_inode.volume.get_inode(entry_inode_idx, entry_type)
        entry_inode_path = root_path + '/' + entry_name
        mode = self.__get_octal_perm(entry_inode.mode_str)
        uid = entry_inode.inode.i_uid
        gid = entry_inode.inode.i_gid
        con = ''

        # loop over xattr ('security.selinux', b'u:object_r:vendor_file:s0\x00')
        for i in list(entry_inode.xattrs()):
          if i[0] == 'security.selinux':
            con = i[1].decode('utf-8')  # decode context
            con = con[:-1]  # remove last car from context '\x00'
          else:
            pass

        file_name_context = '/'+self.file_name + entry_inode_path
        file_name_config = self.file_name + entry_inode_path
        if self.file_name == 'system':
          file_name_context = entry_inode_path
          file_name_config = entry_inode_path[entry_inode_path.startswith(
            '/') and len('/'):]

        if entry_inode.is_dir:
          self.num_dirs += 1
          scan_dir(entry_inode, entry_inode_path)  # loop inside the directory
          self.fs_config.append(f'{file_name_config} {uid} {gid} {mode}')
          self.fs_context.append(f'{file_name_context} {con}')

        elif entry_inode.is_file:
          self.num_files += 1
          self.fs_config.append(f'{file_name_config} {uid} {gid} {mode}')
          self.fs_context.append(f'{file_name_context} {con}')

        elif entry_inode.is_symlink:
          self.num_links += 1
          self.fs_config.append(f'{file_name_config} {uid} {gid} {mode}')
          self.fs_context.append(f'{file_name_context} {con}')

    # open image
    with open(self.image_name, 'rb') as file:
      root = ext4.Volume(file).root
      scan_dir(root)

    self.__write_context()
    self.__write_config()
    self.__write_fetures()
    print(f'{self.num_dirs} DIR {self.num_files} FILE {self.num_links} LINKS')


class FsFetures():
  def __init__(self):
    pass


if __name__ == '__main__':
  if sys.argv.__len__() < 3:
    print(f'USAGE: {sys.argv[0]} image_path info_path')
  else:
    print(
      f':: Save Information {ReadExt4().file_name}.img...',
      f':: Image path -> {ReadExt4().image_name}',
      f':: Info dir   -> {ReadExt4().out_dir}',
      sep='\n', end='\n\n')
    ReadExt4().read_ext4()
