# TO-DO LIST:
#save the content of the workspaces with (a) json file(s)
#add delete+archive interactions(might need something like items id to pull this off)
def change_list_name(self,new_list_name,renamed_list):
    if not new_list_name:
        print("A card cannot have no name. Please enter another name")
    elif new_list_name in self.cards:
        print("This name already exists. Please enter another name")
    else:
        renamed_list.name=new_list_name
class Board:
    """
    Represents a board within a workspace.
    In a full application, this class would manage lists, cards, etc.
    P. Note:only create_list
    """
    def __init__(self, name="Default Board", workspace_instance=None):
        """
        Initializes a Board.
        Args:
            name (str): The name of the board.
            workspace_instance (workspace, optional): A reference to the parent workspace.
        """
        self.name = name
        self.workspace = workspace_instance # Link to the parent workspace
        self.lists = []  # Placeholder for board content (e.g., lists of cards)
        # print(f"DEBUG: Board '{self.name}' initialized/linked for workspace '{workspace_instance.name if workspace_instance else 'None'}'.")

    def __str__(self):
        return f"Board(Name: '{self.name}', Lists: {len(self.lists)})"

    def to_dict(self):
        return {"name": self.name, "lists_count": len(self.lists), "lists": self.list.to_dict} # Example data

    @classmethod
    def from_dict(cls, data: dict, workspace_instance=None):
        """
        Creates a Board object from a dictionary representation.
        Minimal implementation; a real app would deserialize lists, cards, etc.
        Args:
            data (dict): The dictionary containing board data.
            workspace_instance (workspace, optional): The parent workspace instance.
        """
        return cls(name=data.get("name", "Unnamed Board from data"), workspace_instance=workspace_instance)
    def create_list(self,new_list_name,new_description):
        self.lists.append(List(new_list_name,new_description))

class List:
    """
    List in a board. Containing cards. 
    IMPORTANT: Correct me if i'm wrong but we don't need smth like workspace_instance right???
    """
    def change_description(self,new_description,name):
        if new_description:
            self.description=new_description
            self.name=name
    def __init__(self, name, description="There's no description= for this list"):
        self.name=name
        self.description=description
        self.cards=[]
    #def create_card(self, new_card_name="None", new_card_description=None):
    #    self.cards.append(Card(new_card_name,new_card_description)        
    def change_name(self,new_name):
        if new_name:
            self.name=new_name
        else:
            print("A list cannot have no name. Please enter the name")
    def change_description(self,new_description):
        if new_description:
            self.description=new_description
        else: #No description
            self.description="There's no description for this list"
    def change_card_name(self,new_card_name,renamed_card):
        if not new_card_name:
            print("A card cannot have no name. Please enter another name")
        elif new_card_name in self.cards:
            print("This name already exists. Please enter another name")
        else:
            renamed_card.name=new_card_name
    def to_dict(self):
        return {"list_name": self.name, "Description": self.description, "cards_count": len(self.cards), "cards": self.cards.to_dict()}#this is a bit stupid cuz i just realized that i can't save the board like how i'll save the lists
    
    @classmethod
    def from_dict(cls, data):
        return cls(name=data.get("list_name", "Description", "cards_count"))
class Card:
    def __init__(self,name, description="There's no description= for this list"):
        self.name=name
        self.description=description
    
    def change_description(self,new_description):
        if new_description:
            self.description=new_description
    def to_dict(self):
        return {"card_name": self.name, "card_description": self.description}
    
    @classmethod
    def from_dict(cls, data):
        return cls(name=data.get("card_name","card_description"))
    #testing