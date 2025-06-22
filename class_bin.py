# Để riêng một file để thuận tiện check nha
class Bin:
    def __init__(self):
        self.archived_lists = []
        self.archived_cards = []

    def move_list_to_bin(self, list_object: 'List'):
        if not any(l.list_id == list_object.list_id for l in self.archived_lists):
            self.archived_lists.append(list_object)
            return True
        return False
    
    def get_deleted_lists(self):
        return self.archived_lists

    def restore_list(self, item_name: str):
        list_to_restore = next((l for l in self.archived_lists if l.list_name == item_name), None)
        if list_to_restore:
            self.archived_lists.remove(list_to_restore)
        return list_to_restore

    def permanently_delete_list(self, item_name: str) -> bool:
        initial_len = len(self.archived_lists)
        self.archived_lists = [l for l in self.archived_lists if l.list_name != item_name]
        return len(self.archived_lists) < initial_len

    def move_card_to_bin(self, card_object: 'Card'):
        if not any(c.card_id == card_object.card_id for c in self.archived_cards):
            self.archived_cards.append(card_object)

    def to_dict(self):
        return {
            "archived_lists": [lst.to_dict() for lst in self.archived_lists],
            "archived_cards": [card.to_dict() for card in self.archived_cards]
        }

    @classmethod
    def from_dict(cls, data: dict):
        bin_obj = cls()
        if not data:
            return bin_obj
        
        for list_data in data.get("archived_lists", []):
            bin_obj.move_list_to_bin(List.from_dict(list_data))
        for card_data in data.get("archived_cards", []):
            bin_obj.move_card_to_bin(Card.from_dict(card_data))
            
        return bin_obj