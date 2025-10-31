"""
Chatbot module for Parking Management System
"""

import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from pymongo import MongoClient
import re

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")  # Default to gemini-1.5-flash

if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model=model,
    api_key=api_key,
    temperature=0.3,
)

@tool
def visitors_data_from_db(query: str) -> str:
    """
    Fetch parking visitors from MongoDB database. 
    
    ONLY use this tool when the user explicitly asks about:
    - Parking visitors
    - Visitors from the database
    - Who is parked
    - Visitor information (IC, license plate, unit number)
    - Current parking status
    
    DO NOT use this tool for:
    - General knowledge questions
    - Greetings or casual conversation
    - Questions about topics not related to parking/visitors
    
    Args:
        query: The user's question about visitors.
    
    Returns:
        A formatted string of visitors from the database or an error message
    """
    try:
        client = MongoClient(os.getenv("MONGODB_ATLAS_CLUSTER_URI"))
        db = client["parking_manager_db"]
        collection = db["visitors"]

        visitors = list(collection.find({}).limit(20))

        if visitors:
            result = [f"📋 **Total Visitors Found:** {len(visitors)}\n"]
            
            for i, visitor in enumerate(visitors, 1):
                # Format datetime if available
                reg_time = visitor.get('created_at', 'N/A')
                if reg_time != 'N/A' and hasattr(reg_time, 'strftime'):
                    reg_time = reg_time.strftime('%Y-%m-%d %H:%M')
                elif reg_time != 'N/A':
                    reg_time = str(reg_time)
                
                visitor_info = f"""
**{i}. {visitor.get('name', 'N/A')}**
   - 🪪 IC: {visitor.get('ic_number', 'N/A')}
   - 🚗 Plate: {visitor.get('license_plate', 'N/A')}
   - 🏢 Unit: {visitor.get('unit_number', 'N/A')}
   - 📍 Status: {visitor.get('status', 'N/A').capitalize()}
   - 🕐 Registered: {reg_time}
"""
                result.append(visitor_info)
            
            return "\n".join(result)
        else:
            return "No visitors found in the database."
            
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        client.close()


@tool
def count_active_visitors(query: str) -> str:
    """
    Count active visitors currently parked.
    
    Use when user asks:
    - How many visitors?
    - How many active?
    - How many parked?
    """
    try:
        client = MongoClient(os.getenv("MONGODB_ATLAS_CLUSTER_URI"))
        db = client["parking_manager_db"]
        collection = db["visitors"]

        # Check both lowercase and uppercase
        active_count = collection.count_documents({"status": "active"})
        if active_count == 0:
            active_count = collection.count_documents({"status": "Active"})
        
        left_count = collection.count_documents({"status": "left"})
        if left_count == 0:
            left_count = collection.count_documents({"status": "Left"})
        
        total_count = collection.count_documents({})
        total_spots = 105
        available = total_spots - active_count
        occupancy_rate = (active_count / total_spots * 100) if total_spots > 0 else 0
                
        # Assume 105 total spots (update if needed)
        total_spots = 105
        available = total_spots - active_count
        
        return f"Active visitors: {active_count}\nTotal registered: {total_count}\nAvailable spots: {available}/{total_spots}"
        
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        client.close()


@tool
def search_visitor_by_name(name: str) -> str:
    """
    Search for a visitor by name.
    
    Use when user asks:
    - Find visitor X
    - Search for X
    - Is X parked?
    """
    try:
        client = MongoClient(os.getenv("MONGODB_ATLAS_CLUSTER_URI"))
        db = client["parking_manager_db"]
        collection = db["visitors"]

        visitor = collection.find_one({"name": {"$regex": name, "$options": "i"}})
        
        if visitor:
            reg_time = visitor.get('created_at', 'N/A')
            if reg_time != 'N/A' and hasattr(reg_time, 'strftime'):
                reg_time = reg_time.strftime('%Y-%m-%d %H:%M')
            
            return f"""✅ Found visitor:
👤 Name: {visitor.get('name', 'N/A')}
🪪 IC: {visitor.get('ic_number', 'N/A')}
🚗 Plate: {visitor.get('license_plate', 'N/A')}
🏢 Unit: {visitor.get('unit_number', 'N/A')}
📍 Status: {visitor.get('status', 'N/A')}
🕐 Registered: {reg_time}"""

        else:
            return f"No visitor found with name '{name}'."
            
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        client.close()


@tool
def get_visitors_by_unit(unit_number: str) -> str:
    """
    Get visitors for a specific unit.
    
    Use when user asks:
    - Visitors for unit X
    - Who visited unit Y?
    """
    try:
        client = MongoClient(os.getenv("MONGODB_ATLAS_CLUSTER_URI"))
        db = client["parking_manager_db"]
        collection = db["visitors"]

        visitors = list(collection.find({"unit_number": unit_number}))
        
        if visitors:
            result = [f"Found {len(visitors)} visitors for unit {unit_number}:\n"]
            for i, visitor in enumerate(visitors, 1):
                result.append(
                    f"{i}. {visitor.get('name')} - {visitor.get('license_plate')} ({visitor.get('status')})"
                )
            return "\n".join(result)
        else:
            return f"No visitors found for unit {unit_number}."
            
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        client.close()

@tool
def get_parking_summary(query: str) -> str:
    """Get a quick summary of parking status."""
    try:
        client = MongoClient(os.getenv("MONGODB_ATLAS_CLUSTER_URI"))
        db = client["parking_manager_db"]
        collection = db["visitors"]

        active = collection.count_documents({"status": {"$regex": "^active$", "$options": "i"}})
        total_spots = 105
        available = total_spots - active
        
        if available == 0:
            status = "🔴 PARKING FULL"
        elif available < 20:
            status = "🟡 LOW AVAILABILITY"
        else:
            status = "🟢 PARKING AVAILABLE"
        
        return f"{status}\n{active} cars parked, {available} spots available"
        
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        client.close()



# Export tools
tools = [
    visitors_data_from_db,
    count_active_visitors,
    search_visitor_by_name,
    get_visitors_by_unit,
    get_parking_summary
]


# CHATBOT CLASS

class ParkingChatbot:
    """Main chatbot class for parking management."""
    
    def __init__(self):
        """Initialize chatbot with LLM and tools."""
        self.llm = llm
        self.tools = tools
        self.is_available = True if api_key else False

    def _classify_intent(self, query: str) -> tuple:
        """
        Classify user intent from query.
        Returns: (intent_type, extracted_data)
        """
        query_lower = query.lower()
        
        # 🆕 NEW: Detect "how-to" questions (instructional)
        if any(phrase in query_lower for phrase in 
               ['how can i', 'how do i', 'how to', 'what are the ways', 
                'tell me how', 'explain how', 'show me how']):
            return ('how_to', None)
        
        # Count/Stats intent
        if any(word in query_lower for word in 
               ['how many', 'count', 'stats', 'statistics', 'occupancy', 
                'available', 'free', 'spots', 'capacity']):
            return ('stats', None)
        
        # Status/Summary intent
        if any(word in query_lower for word in 
               ['status', 'summary', 'overview', 'situation', 'full', 'busy']):
            return ('summary', None)
        
        # Search by name intent (only if NOT a how-to question)
        if any(word in query_lower for word in 
               ['search for', 'find visitor', 'locate visitor', 'look for visitor', 'where is', 'is there a visitor']):
            # Extract name (capitalize first letter of each word)
            words = query.split()
            # Get words that are likely names (not common words)
            exclude = {'search', 'find', 'for', 'visitor', 'named', 'called', 
                      'the', 'a', 'an', 'is', 'there', 'where', 'who', 'locate',
                      'how', 'can', 'i', 'do', 'to', 'tell', 'me', 'explain', 'show'}
            names = [w.capitalize() for w in words 
                    if len(w) > 2 and w.lower() not in exclude and not w.isdigit()]
            if names:
                return ('search', names[0])
            return ('search', None)
        
        # Unit query intent
        if any(word in query_lower for word in ['unit', 'apartment', 'flat']):
            # Extract unit number (e.g., B-1-01, A-74, B1-09)
            unit_pattern = r'[A-Z]-?\d+-?\d*'
            matches = re.findall(unit_pattern, query.upper())
            if matches:
                return ('unit', matches[0])
            # Try simpler pattern
            words = query.split()
            units = [w.upper() for w in words if any(c.isdigit() for c in w) and any(c.isalpha() for c in w)]
            if units:
                return ('unit', units[0])
            return ('unit', None)
        
        # List all visitors intent
        if any(word in query_lower for word in 
               ['list', 'show all', 'display', 'view all', 'see all', 'visitors']):
            return ('list', None)
        
        # Greeting
        if any(word in query_lower for word in ['hello', 'hi', 'hey', 'greetings']):
            return ('greeting', None)
        
        # Help
        if any(word in query_lower for word in ['help', 'what can you', 'how to use']):
            return ('help', None)
        
        return ('general', None)
    
    def get_response(self, query: str) -> str:
        """
        Get chatbot response for user query.
        
        Args:
            query: User's question
            
        Returns:
            Chatbot's response
        """
        if not self.is_available:
            return "⚠️ Chatbot unavailable. Please check GOOGLE_API_KEY in .env file."
        
        try:
            # Classify the user's intent
            intent, extracted_data = self._classify_intent(query)
            
            # Handle different intents
            if intent == 'greeting':
                return "👋 Hello! I'm your parking assistant. I can help you with:\n• Checking parking availability\n• Finding specific visitors\n• Viewing visitor lists\n• Searching by unit number\n\nWhat would you like to know?"
            
            elif intent == 'help':
                return """🤖 **How I can help you:**

📊 **Check Statistics:**
• "How many visitors are parked?"
• "What's the parking status?"
• "How many spots available?"

🔍 **Search Visitors:**
• "Find visitor John"
• "Search for visitor named Alice"
• "Is there a visitor called Mike?"

📋 **View Lists:**
• "Show all visitors"
• "List all parked cars"

🏢 **Search by Unit:**
• "Show visitors for unit B-1-01"
• "Who visited unit A-74?"

Just ask naturally!"""
            
            elif intent == 'how_to':
                # 🆕 NEW: Handle instructional questions
                if 'search' in query.lower() or 'find' in query.lower():
                    return """🔍 **How to Search for Visitors:**

You can search for visitors in several ways:

1️⃣ **By Name:** Ask me "Find visitor [Name]" or "Search for [Name]"
   - Example: "Find visitor John"

2️⃣ **By License Plate:** Go to the "View All Visitors" tab and use the search bar at the top

3️⃣ **By Unit Number:** Ask me "Show visitors for unit [Unit#]"
   - Example: "Show visitors for unit B-1-01"

Just ask me naturally and I'll help you find who you're looking for! 😊"""
                
                elif 'unit' in query.lower():
                    return """🏢 **How to Find Visitors by Unit:**

To find all visitors for a specific unit, you can:

1️⃣ **Ask me directly:** "Show visitors for unit [Unit Number]"
   - Example: "Show visitors for unit B-1-01"
   - Example: "Who visited unit A-74?"

2️⃣ **Use the View tab:** Go to "View All Visitors" and use the "Unit Number" filter dropdown

I'll show you the name, license plate, and status of all visitors for that unit! 🚗"""
                
                else:
                    return """💡 **General Instructions:**

I can help you with:
• **Searching visitors** - Ask "How can I search for visitors?"
• **Finding by unit** - Ask "How to find visitors by unit?"
• **Checking availability** - Ask "How many spots are available?"
• **Viewing lists** - Just say "Show all visitors"

What would you like to know? 😊"""
            
            elif intent == 'stats':
                tool_result = count_active_visitors.invoke({"query": ""})
                context = tool_result
            
            elif intent == 'summary':
                tool_result = get_parking_summary.invoke({"query": ""})
                context = tool_result
            
            elif intent == 'search':
                if extracted_data:
                    tool_result = search_visitor_by_name.invoke({"name": extracted_data})
                    context = tool_result
                else:
                    return "🔍 Please specify a visitor name. Example: 'Find visitor John'"
            
            elif intent == 'unit':
                if extracted_data:
                    tool_result = get_visitors_by_unit.invoke({"unit_number": extracted_data})
                    context = tool_result
                else:
                    return "🏢 Please specify a unit number. Example: 'Show visitors for unit B-1-01'"
            
            elif intent == 'list':
                tool_result = visitors_data_from_db.invoke({"query": ""})
                context = tool_result
            
            else:
                # General query - let LLM decide
                context = "I can help with visitor info, parking stats, and searching. Please ask about visitors, parking availability, or specific units."
            
            
            # Generate response using LLM
            prompt = f"""You are a friendly parking management assistant. Respond naturally and helpfully.

IMPORTANT: When you have visitor data, you MUST display it completely. Never summarize or say "followed by..." - always show the full list.

Context/Data: {context}

User Question: {query}

Instructions:
- If context contains visitor information, display ALL of it in a clear, readable format
- Use bullet points or numbered lists for multiple visitors
- Include all details provided (name, IC, plate, unit, status)
- Be concise but COMPLETE - never truncate or summarize the data
- If no data is available, say so clearly

Provide your response:"""
            
            response = self.llm.invoke(prompt)
            return response.content
            
        except Exception as e:
            return f"Error: {str(e)}"


# Singleton instance
_chatbot_instance = None

def get_chatbot() -> ParkingChatbot:
    """Get or create chatbot instance."""
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = ParkingChatbot()
    return _chatbot_instance


# TEST FUNCTION

if __name__ == "__main__":
    print("🤖 Testing Parking Chatbot...\n")
    
    bot = get_chatbot()
    
    if bot.is_available:
        print("✅ Chatbot initialized!\n")
        
        # Test queries
        tests = [
            "How many visitors are parked?",
            "Show all visitors",
            "How can I search for a visitor?",
            "Find visitor John"
        ]
        
        for test_query in tests:
            print(f"❓ Q: {test_query}")
            response = bot.get_response(test_query)
            print(f"🤖 A: {response}\n")
    else:
        print("❌ Chatbot unavailable. Check API key.")