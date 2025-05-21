import easygui
import os
import json
class workspace(board):
    def __init__(self,name,pwd=None,last_edited='0'):
        self.name=name
        self.pwd=pwd
        self.last_edited=last_edited

    def set_password(self, new_password):
        self.pwd=new_password
    def check_password(self,input_password):
        if self.pwd==input_password or self.pwd is None:
            wm.load_workspace()
        else:
            self._notify("The password is incorrect", use_gui=False)
#    def update_last_edited(self):(how tf do i do this)
#    def get_board(self,board):
#        load_board(don't we have to create the board in order to load it????)
new_password=easygui.passwordbox(msg="Please enter the new password:", title="New Password")
if new_password is None: # User pressed Cancel
        print("Password creation cancelled.")
elif not new_password.strip():
    wm.pwd=None
else:
    path_input = easygui.diropenbox(msg="Select the parent directory for the new workspace:", title="Create Workspace")
    if path_input is None: # User pressed Cancel
        print("Password creation cancelled.")
    else:
        # create_workspace method will handle validation and user notification for the inputs
        wm.set_password(new_password)
#maybe we should put the following lines into load_workspace
if wm.pwd is not None:
    input_password=easygui.passwordbox(msg="What is the workspace password?", title="Password")
    wm.check_password(input_password)

 