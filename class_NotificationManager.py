class NotificationManager:
    def __init__(self):
        self.notifications = {}

    def register_notification(self, card: Card):
        if card.deadline:
            print(f"DEBUG: Registering notification for card '{card.name}'")
            self.notifications[card.card_id] = {'deadline': card.deadline, 'status': 'active'}
            
    def disable_notification(self, card_id: str):
        if card_id in self.notifications:
            print(f"DEBUG: Disabling notification for card ID {card_id[:8]}...")
            self.notifications[card_id]['status'] = 'inactive'

    def enable_notification(self, card_id: str):
        if card_id in self.notifications:
            print(f"DEBUG: Enabling notification for card ID {card_id[:8]}...")
            self.notifications[card_id]['status'] = 'active'