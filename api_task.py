from pymongo import MongoClient
from datetime import datetime, UTC
from bson.objectid import ObjectId
from dotenv import load_dotenv
import os
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status
from typing import List, Optional, Dict, Any
from database_task import DatabaseManager
import uvicorn 

load_dotenv()

app = FastAPI(title="Visitor Parking Management API", version="1.0.0")

# --- INSTANTIATE DB MANAGER (Following the requested format) ---
try:
    db = DatabaseManager()
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    db = None

# Pydantic models for request/response

class VisitorCreate(BaseModel):
    name: str = Field(..., min_length=1)
    ic_number: str = Field(..., min_length=1)  # Changed from IC_number to ic_number
    license_plate: str = Field(..., min_length=1)
    unit_number: str = Field(..., min_length=1)

class VisitorStatusUpdate(BaseModel):
    """Schema for updating only the visitor's status."""
    status: str 

class VisitorResponse(BaseModel):
    """Schema for the full visitor response object returned by the API."""
    id: str 
    name: str
    ic_number: str  # This is what we expect
    license_plate: str
    unit_number: str
    status: str
    registered_at: datetime = Field(alias='created_at')
    
    class Config:
        populate_by_name = True
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# --- Endpoints ---

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint that provides API information"""
    return {
        "message": "Welcome to the Visitor Parking Management API",
        "version": "1.0",
        "endpoints": {
            "visitors": "/visitors/",
            "docs": "/docs"
        }
    }

@app.post("/visitors/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED, tags=["Visitors"])
async def create_visitor_endpoint(visitor: VisitorCreate):
    """
    Register a new visitor with their name, IC number, license plate, and unit number.
    The IC number and license plate must be unique.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection failed.")
        
    # The database function now requires the IC_number
    result, success = db.create_visitor(
        visitor.name, 
        visitor.ic_number, 
        visitor.license_plate, 
        visitor.unit_number
    )
    
    if not success:
        # Handles the duplicate key error from the database manager
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("detail", "Failed to create visitor due to unknown error.")
        )
    
    # Returns the successful creation message and ID
    return result

@app.get("/visitors/", response_model=List[VisitorResponse], tags=["Visitors"])
async def get_all_visitors_endpoint():
    """Retrieve a list of all registered visitors."""
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Database connection failed."
        )
    
    visitors = db.get_all_visitors()
    
    # Convert the visitors data to match the response model
    formatted_visitors = []
    for visitor in visitors:
        try:
            # Convert _id to id and standardize field names
            visitor_data = {
                'id': str(visitor.pop('_id')),
                'name': visitor.get('name', ''),
                'ic_number': visitor.get('ic_number') or visitor.get('IC_number', ''),  # Try both field names
                'license_plate': visitor.get('license_plate', ''),
                'unit_number': visitor.get('unit_number', ''),
                'status': visitor.get('status', 'Active'),
            }

            # Handle created_at datetime
            created_at = visitor.get('created_at')
            if isinstance(created_at, str) and created_at != 'N/A':
                visitor_data['created_at'] = datetime.fromisoformat(created_at.replace(' ', 'T'))
            elif isinstance(created_at, datetime):
                visitor_data['created_at'] = created_at
            else:
                visitor_data['created_at'] = datetime.now(UTC)

            # Only add visitor if required fields are present
            if visitor_data['ic_number']:  # Skip visitors without IC numbers
                formatted_visitors.append(visitor_data)
            
        except Exception as e:
            print(f"Error processing visitor {visitor.get('_id', 'unknown')}: {e}")
            continue
    
    return formatted_visitors

@app.put("/visitors/{visitor_id}/status", response_model=Dict[str, Any], tags=["Visitors"])
async def update_visitor_status_endpoint(visitor_id: str, status_data: VisitorStatusUpdate):
    """Update a visitor's status (Active or Left) using their ID."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection failed.")
        
    # Calls the specific update_visitor_status function
    result, success = db.update_visitor_status(visitor_id, status_data.status)
    
    if not success:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in result.get("detail", "") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get("detail", "Failed to update visitor status.")
        )
    
    return result

@app.delete("/visitors/{visitor_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Visitors"])
async def delete_visitor_endpoint(visitor_id: str):
    """Delete a visitor record using their ID."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection failed.")
        
    result, success = db.delete_visitor(visitor_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("detail", "Visitor not found or deletion failed.")
        )
    
    return 

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)