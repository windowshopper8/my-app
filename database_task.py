from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from dotenv import load_dotenv
from typing import Tuple, Dict, Any, List    
import os

load_dotenv()

mongo_uri = os.getenv('MONGODB_ATLAS_CLUSTER_URI')


class DatabaseManager:
    """
    Manages all CRUD operations for visitor parking records in MongoDB.
    """
    def __init__(self, db_name='parking_manager_db', connection_string: str = mongo_uri):
        """
        Initializes the MongoDB connection and collections.
        (Note: Connection errors are handled externally or by MongoClient)
        """
        self.client = MongoClient(connection_string)
        self.db = self.client[db_name]
        self.visitors_collection = self.db.visitors
        self.init_database()

    def init_database(self):
        """Initialize database with collections and indexes."""
        # Drop existing indexes first
        self.visitors_collection.drop_indexes()
        
        # Create unique indexes with consistent field names
        self.visitors_collection.create_index("ic_number", unique=True)
        self.visitors_collection.create_index("license_plate", unique=True)
        self.visitors_collection.create_index("unit_number")

    def create_visitor(self, name: str, ic_number: str, license_plate: str, unit_number: str) -> tuple[dict, bool]:
        try:
            # Validate input
            if not ic_number or not license_plate:
                return {"detail": "IC number and license plate are required"}, False
            
            # Print debug info
            print(f"Trying to insert - IC: {ic_number}, Plate: {license_plate}")
            
            # Check for existing visitor with case-insensitive search
            existing = self.visitors_collection.find_one({
                "$or": [
                    {"ic_number": ic_number.upper()},
                    {"license_plate": license_plate.upper()}
                ]
            })

            if existing:
                duplicate_field = "IC number" if existing.get("ic_number") == ic_number.upper() else "license plate"
                return {"detail": f"Visitor with this {duplicate_field} already exists"}, False

            # Create new visitor with standardized fields
            new_visitor = {
                "name": name,
                "ic_number": ic_number.upper(),  # Note: consistent field name
                "license_plate": license_plate.upper(),
                "unit_number": unit_number,
                "created_at": datetime.now(),
                "status": "active"
            }

            result = self.visitors_collection.insert_one(new_visitor)
            return {
                "detail": "Visitor created successfully",
                "visitor_id": str(result.inserted_id)
            }, True

        except Exception as e:
            print(f"Database error details: {str(e)}")  # Debug print
            return {"detail": f"Database error: {str(e)}"}, False
        
    def get_all_visitors(self) -> List[Dict[str, Any]]:
        """Retrieves all visitor records, converting ObjectId to string"""
        try:
            # Sort by creation time, newest first
            visitors = list(self.visitors_collection.find().sort("created_at", -1))
            
            # Convert ObjectID to string and format datetime
            for visitor in visitors:
                visitor['_id'] = str(visitor['_id'])
                # Handle datetime formatting safely
                if 'created_at' in visitor:
                    visitor['created_at'] = visitor['created_at'].strftime('%Y-%m-%d %H:%M')
                else:
                    visitor['created_at'] = "N/A"
            return visitors
        except Exception as e:
            print(f"Error fetching visitors: {e}")
            return []

    def update_visitor_status(self, visitor_id: str, new_status: str) -> Tuple[Dict[str, Any], bool]:
        """Updates the status of a specific visitor"""
        try:
            if not ObjectId.is_valid(visitor_id):
                return {"detail": "Invalid visitor ID format."}, False
            
            visitor_object_id = ObjectId(visitor_id)
            
            result = self.visitors_collection.update_one(
                {"_id": visitor_object_id},
                {"$set": {
                    "status": new_status,
                    "last_updated": datetime.now()
                }}
            )

            if result.modified_count > 0:
                return {"message": "Visitor status updated successfully"}, True
            return {"detail": "Visitor not found or status already set."}, False

        except Exception as e:
            return {"detail": f"Error updating visitor status: {str(e)}"}, False

    def delete_visitor(self, visitor_id: str) -> Tuple[Dict[str, Any], bool]:
        """Deletes a visitor record by ID"""
        try:
            if not ObjectId.is_valid(visitor_id):
                return {"detail": "Invalid visitor ID format."}, False

            visitor_object_id = ObjectId(visitor_id)
            result = self.visitors_collection.delete_one({"_id": visitor_object_id})
            
            if result.deleted_count > 0:
                return {"message": "Visitor deleted successfully"}, True
            return {"detail": "Visitor not found."}, False

        except Exception as e:
            return {"detail": f"Error deleting visitor: {str(e)}"}, False


    def close_connection(self):
        """Closes the MongoDB connection."""
        self.client.close()
        

# --- Interactive CLI Menu for Local Testing ---
# This part helps you verify the database file independently.

def display_menu():
    """Display the main menu."""
    print("\n" + "="*40)
    print("    VISITOR PARKING DATABASE MANAGER")
    print("="*40)
    print("1. Register New Visitor")
    print("2. View All Visitors")
    print("3. Update Visitor Status (Left/Active)")
    print("4. Delete Visitor")
    print("5. Exit")
    print("-"*40)

def main():
    """Main interactive CLI function."""
    try:
        # Initialize the database manager instance
        db = DatabaseManager()
        print("Connected to MongoDB successfully!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        print("Please ensure your MONGO_URI in the .env file is correct.")
        return

    while True:
        display_menu()
        choice = input("Enter your choice (1-5): ").strip()

        if choice == '1':
            print("\n--- Register New Visitor ---")
            name = input("Enter visitor name: ").strip()
            ic_number = input("Enter visitor IC Number (Unique): ").strip()
            license_plate = input("Enter license plate (Unique): ").strip()
            unit_number = input("Enter unit number visiting: ").strip()

            result, success = db.create_visitor(name, ic_number, license_plate, unit_number)
            if success:
                print(f"✅ Success! Visitor ID: {result.get('visitor_id')}")
            else:
                print(f"❌ Failed to create visitor. Reason: {result.get('detail', 'Unknown error')}")

        elif choice == '2':
            print("\n--- All Visitors ---")
            visitors = db.get_all_visitors()
            if visitors:
                for v in visitors:
                    print(f"ID: {v['_id'][:8]}... | "
                          f"Plate: {v['license_plate']} | "
                          f"Name: {v['name']} | "
                          f"Unit: {v['unit_number']} | "
                          f"Status: {v['status']} | "
                          f"Created: {v['created_at']}")  # Datetime is already formatted
            else:
                print("No visitors found.")

        elif choice == '3':
            print("\n--- Update Visitor Status ---")
            visitor_id = input("Enter Visitor ID to update status: ").strip()
            new_status = input("Enter new status (Active/Left): ").strip()
            
            if new_status not in ["Active", "Left"]:
                print("Invalid status. Must be 'Active' or 'Left'.")
                continue

            result, success = db.update_visitor_status(visitor_id, new_status)
            if success:
                print(f"✅ Status updated successfully for ID {visitor_id}")
            else:
                print(f"❌ Failed to update status. Reason: {result.get('detail', 'Unknown error')}")

        elif choice == '4':
            print("\n--- Delete Visitor ---")
            visitor_id = input("Enter Visitor ID to delete: ").strip()
            confirm = input(f"Are you sure you want to delete record {visitor_id}? (y/n): ")
            if confirm.lower() == 'y':
                result, success = db.delete_visitor(visitor_id)
                if success:
                    print("✅ Visitor deleted successfully!")
                else:
                    print(f"❌ Deletion failed. Reason: {result.get('detail', 'Unknown error')}")
            else:
                print("Deletion cancelled.")

        elif choice == '5':
            print("\nClosing database connection.. Goodbye!")
            db.close_connection()
            break

        else:
            print("Invalid choice. Please enter 1-5.")

        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()