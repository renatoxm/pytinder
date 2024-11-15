import os
import json

class Dialog:
    PREFIX = """
        You are now playing the role of [Sender] and your task is to respond to [Receiver] in the conversation below. Your response should not exceed 50 words and end with a question. Please respond in the language used by [Sender].
    """

    def generate_input(self, from_user_id, to_user_id, dialog):
        context = '\n'.join([str(d).replace(from_user_id, '[Sender]').replace(to_user_id, '[Receiver]') for d in dialog])
        return f'{self.PREFIX} \n\n{context}\n[Sender]:'

    def export_message_json(self, user_id, dialog):
            receiver_id = dialog[0].to_id if dialog[0].from_id == user_id else dialog[0].from_id
            messages = [{
                "role": "system",
                "content": self.PREFIX
            }]
            for d in dialog:
                if d.from_id == user_id:
                    messages.append({
                        "role": "assistant",
                        "content": d.message
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": d.message
                    })
            file_name = f"chat_data/{user_id}/{receiver_id}.json"
            folder_path = os.path.dirname(file_name)
            os.makedirs(folder_path, exist_ok=True)
            with open(file_name, "w", encoding="utf-8") as f:
                json.dump({"messages": messages}, f, ensure_ascii=False, indent=4)