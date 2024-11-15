from src.models import ModelInterface

class ChatGPT:
    def __init__(self, model: ModelInterface):
        self.model = model

    def get_response(self, interests: str, bio: str, text: str, language: str) -> str:
        messages = [{
            'role': 'system',
            'content': '''
                This chatbot will act on behalf of the user to chat with other girls on the dating app. The chatbot should follow these guidelines to ensure engaging and natural conversations:
                1. Keep the conversation light, natural, and not awkward.
                2. Infuse humor and fun into the conversation.
                3. Base the conversation on the user's initial provided basic information.
                4. End messages with questions to encourage ongoing dialogue.
                5. Respond based on previous chat history provided.
                6. The goal of the conversation is to explore the girl's interests and eventually invite her out.
                7. Translate the conversation to {language}.
                User Information: 
                    - Bio: {bio}
                    - Interests: {interests}
            '''
        }, {
            'role': 'user', 'content': text
        }]
        response = self.model.chat_completion(messages)
        content = response['choices'][0]['message']['content']
        return content


class DALLE:
    def __init__(self, model: ModelInterface):
        self.model = model

    def generate(self, text: str) -> str:
        return self.model.image_generation(text)
