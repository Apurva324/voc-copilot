import os
from PIL import Image, ImageDraw, ImageFont

# A list of realistic scenarios between Zomato delivery partners, customers, and support agents
SCENARIOS = [
    {
        "filename": "mock_whatsapp_1.png",
        "title": "Zomato Delivery Partner",
        "sender_msg": "Delivery: Sir I have reached your gate but guard\nis not letting me in.",
        "receiver_msg": "Customer: The app is showing you are 2km away!\nWhy is the GPS wrong?"
    },
    {
        "filename": "mock_whatsapp_2.png",
        "title": "Zomato Support Agent",
        "sender_msg": "Support: Hello, I am looking into your missing item\nrefund request now.",
        "receiver_msg": "Customer: The delivery guy forgot half my order!\nI want my money back instantly."
    },
    {
        "filename": "mock_whatsapp_3.png",
        "title": "Zomato Delivery Partner",
        "sender_msg": "Delivery: Ma'am your order is delayed due to heavy\nrain near Indiranagar.",
        "receiver_msg": "Customer: It has been 90 minutes. The app tracking\nis completely frozen."
    },
    {
        "filename": "mock_whatsapp_4.png",
        "title": "Zomato Support Chatbot",
        "sender_msg": "Bot: Please upload a clear photo of the damaged\npackaging to proceed.",
        "receiver_msg": "Customer: The gravy completely spilled inside the bag.\nIt is a total mess."
    },
    {
        "filename": "mock_whatsapp_5.png",
        "title": "Zomato Corporate Desk",
        "sender_msg": "Support: The Zomato Gold coupon code is only valid\non online payments.",
        "receiver_msg": "Customer: It keeps saying 'Invalid Code' even when\nI select credit card checkout!"
    }
]

def generate_all_mock_chats():
    print(" Generating 5 realistic WhatsApp screenshots for testing...")
    
    try:
        font = ImageFont.load_default()
    except IOError:
        font = ImageFont.load_default()

    for idx, chat in enumerate(SCENARIOS):
        # Create a new blank phone screen image
        img = Image.new("RGB", (800, 1000), color="#0b141a")
        canvas = ImageDraw.Draw(img)

        # Draw Header
        canvas.rectangle([(0, 0), (800, 100)], fill="#1f2c34")
        canvas.text((40, 35), chat["title"], fill="#ffffff", font=font)

        # Draw Sender Bubble (Left Aligned)
        canvas.rounded_rectangle([(40, 180), (620, 260)], fill="#202c33", radius=10)
        canvas.text((60, 200), chat["sender_msg"], fill="#e9edef", font=font)

        # Draw Receiver Bubble (Right Aligned)
        canvas.rounded_rectangle([(180, 320), (760, 400)], fill="#005c4b", radius=10)
        canvas.text((200, 340), chat["receiver_msg"], fill="#e9edef", font=font)

        # Save individual file
        img.save(chat["filename"])
        print(f"   ↳ Generated: {chat['filename']}")
        
    print(" Done! Check your project folder for 5 distinct test images.")

if __name__ == "__main__":
    generate_all_mock_chats()