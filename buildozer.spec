[app]

# (str) Title of your application
title = Kanpy

# (str) Package name
package.name = kanpy

# (str) Package domain (needed for Android)
package.domain = org.kanpy

# (str) Package image
package.icon = %(source.dir)s/icon.png

# (str) Source code where the main.py live
# '.' means the current directory
source.dir = .

# (list) Source files to include. Make sure to include all necessary file types.
source.include_exts = png,jpg,kv,py,txt,ttf,json
source.include_patterns = *.py,*.kv,*.txt,*.ttf,*.json

# (list) List of directories to exclude
# We exclude venv to keep the package small.
source.exclude_dirs = tests, bin, venv, .venv, __pycache__

# (str) Application versioning
version = 1.0.5

# (list) Application requirements
# All the python packages your app needs.
requirements = python3,kivy,cryptography,cffi,pycparser,idna

# (str) Presplash of the application
# You can create a loading image at data/presplash.png
# presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
# This is the icon that will be displayed on the device.
icon.filename = %(source.dir)s/icon.png

# (list) Supported orientations
orientation = portrait

#
# Android specific
#

# (list) Android permissions
# WRITE_EXTERNAL_STORAGE is needed because your app saves files.
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,READ_CALENDAR,WRITE_CALENDAR

# (int) Target Android API, should be as high as possible.
android.api = 31

# (int) Minimum API your APK will support.
android.minapi = 21

# (list) The Android archs to build for.
android.archs = arm64-v8a, armeabi-v7a


[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

