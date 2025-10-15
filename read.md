from fastapi import FastAPI, HTTPException, status
from contextlib import asynccontextmanager
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from bson.objectid import ObjectId
from typing import Tuple, Dict, Any, List    
from database_task import DatabaseManager
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Visitor Parking Management API", version="1.0.0")

class VisitorCreate(BaseModel):
  
    name: str
    IC_number: str
    license_plate: str
    unit_number: str

class VisitorStatusUpdate(BaseModel):
    status: str

class VisitorResponse(BaseModel):
    id: str
    name: str
    IC_number: str
    license_plate: str
    unit_number: str
    status: str
    registered_at: str
    last_updated: str
    
class Config:
    populate_by_name = True


class MessageResponse(BaseModel):
    message: str

class ErrorResponse(BaseModel):
    detail: str

# --- INSTANTIATE DB MANAGER ---
try:
    db= DatabaseManager()
except Exception as e:
    print(f"Failed to connect to MongoDB:{e}")
    db = None


# --- Endpoints ---

# [FIX 1] Added Health Check to fix 404 Not Found error
@app.get("/", summary="Health Check")
def read_root():
    """Simple health check endpoint."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection failed at startup.")
    return {"status": "ok", "message": "Visitor Parking Management API is running"}


@app.post("/visitors/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED, tags=["Visitors"])
async def create_visitor_endpoint(visitor: VisitorCreate):
    """
    Register a new visitor with their name, IC number, license plate, and unit number.
    The IC number and license plate must be unique.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection failed.")
        
    result, success = db.create_visitor(
        visitor.name, 
        visitor.IC_number, 
        visitor.license_plate, 
        visitor.unit_number
    )
    
    if not success:
        # Handles the duplicate key error or other database errors
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
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection failed.")
        
    visitors = db.get_all_visitors()
    return visitors

@app.put("/visitors/{visitor_id}/status", response_model=Dict[str, Any], tags=["Visitors"])
async def update_visitor_status_endpoint(visitor_id: str, status_data: VisitorStatusUpdate):
    """Update a visitor's status (Active or Left) using their ID."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection failed.")
        
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
    uvicorn.run(app, host="0.0.0.0", port=8002)
import uvicorn












----------------


import streamlit as st
import requests
import pandas as pd
from typing import List, Dict, Any

# API is expected to run on port 8002
API_BASE_URL = "http://localhost:8002" 
STATUS_OPTIONS = ["Active", "Left"]

# --- API CLIENT FUNCTIONS ---

def check_api_connection():
    """Check if the FastAPI server is running and accessible."""
    try:
        # Check for 200 from the health check endpoint
        response = requests.get(f"{API_BASE_URL}/") 
        return response.status_code == 200
    except:
        return False
    
def get_all_visitors() -> List[Dict[str, Any]]:
    """Get all visitors via API."""
    try: 
        response = requests.get(f"{API_BASE_URL}/visitors/")
        if response.status_code == 200:
            return response.json(), True
        return [], False
    except:
        return [], False

def create_visitor(name: str, ic_number: str, license_plate: str, unit_number: str):
    """
    Register a new visitor via API. 
    Sends the four fields required by the VisitorCreate Pydantic model.
    """
    payload = {
        "name": name, 
        "IC_number": ic_number, 
        "license_plate": license_plate, 
        "unit_number": unit_number
    }
    try:
        response = requests.post(
            f"{API_BASE_URL}/visitors/",
            json=payload
        )
        # 201 Created is expected
        return response.json(), response.status_code == 201
    except Exception as e:
        return {"error": str(e)}, False

def update_visitor_status(visitor_id: str, new_status: str):
    """Update an existing visitor's status via API."""
    try:
        response = requests.put(
            f"{API_BASE_URL}/visitors/{visitor_id}/status",
            json={"status": new_status}
        )
        # 200 OK is expected
        return response.json(), response.status_code == 200
    except Exception as e:
        return {"error": str(e)}, False

def delete_visitor(visitor_id: str):
    """Delete a visitor record via API."""
    try: 
        response = requests.delete(f"{API_BASE_URL}/visitors/{visitor_id}")
        # 204 No Content is expected for successful delete
        return {}, response.status_code == 204
    except Exception as e:
        return {"error": str(e)}, False

# --- STREAMLIT PAGE FUNCTIONS (Build the UI) ---
    
def display_visitor_table(visitors: List[Dict[str, Any]]):
    """Displays all visitors in a styled table format."""
    
    if not visitors:
        st.info("No visitors registered yet.")
        return
        
    # Convert list of dicts to DataFrame for better display
    df = pd.DataFrame(visitors)
    
    # Rename columns for display
    df = df.rename(columns={
        'id': 'ID', 
        'name': 'Visitor Name', 
        'IC_number': 'IC Number', 
        'license_plate': 'License Plate', 
        'unit_number': 'Unit No.', 
        'status': 'Status',
        'registered_at': 'Registered At'
    })

    # Prepare data for display
    # The datetime field is now an ISO string, so we just convert it to datetime object for formatting
    df['Registered At'] = pd.to_datetime(df['Registered At']).dt.strftime('%Y-%m-%d %H:%M')
    df['ID'] = df['ID'].str[:8] + '...' # Truncate ID for readability

    
    st.dataframe(
        df[['ID', 'Visitor Name', 'IC Number', 'License Plate', 'Unit No.', 'Status', 'Registered At']],
        hide_index=True,
        width=True,
        column_config={
            "Status": st.column_config.TextColumn("Status", help="Current visitor status", width="small")
        }
    )

def create_visitor_form():
    """Form to register a new visitor."""
    st.header("Register New Visitor")
    
    with st.form("create_visitor_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Visitor Name")
            license_plate = st.text_input("License Plate (Unique)", placeholder="e.g., JAA1234")
        with col2:
            ic_number = st.text_input("IC Number (Unique)", placeholder="e.g., 901231-14-5678")
            unit_number = st.text_input("Unit Number Visiting", placeholder="e.g., B-1-01")

        submitted = st.form_submit_button("Register Visitor", type="primary")

        if submitted:
            if all([name, ic_number, license_plate, unit_number]):
                result, success = create_visitor(name, ic_number, license_plate, unit_number)
                if success:
                    st.success(f"Visitor '{result.get('name')}' registered successfully with ID: {result.get('id')[:8]}...")
                    st.toast("Registration Complete!", icon="🎉")
                    st.rerun()
                else:
                    st.error(f"Registration failed: {result.get('detail', 'Unknown API error')}")
            else:
                st.error("All fields are required.")

def manage_visitor_status_form(visitors: List[Dict[str, Any]]):
    """Interface to update status or delete a visitor."""
    st.header("Manage Visitor Status & Deletion")

    # Create selection dictionary for dropdown
    options = {
        f"{v['name']} ({v['license_plate']}) - ID: {v['id'][:8]}..." : v['id']
        for v in visitors
    }
    
    selected_display = st.selectbox(
        "Select Visitor to Manage",
        options=list(options.keys()),
        index=None
    )

    if selected_display:
        selected_id = options[selected_display]
        selected_visitor = next(v for v in visitors if v['id'] == selected_id)
        current_status = selected_visitor['status']

        st.markdown(f"**Current Status:** :blue[{current_status}]")
        
        col_status, col_delete = st.columns(2)

        with col_status:
            # Use a slightly different key for the radio button to prevent clashes
            new_status = st.radio(
                "Change Status To:", 
                options=STATUS_OPTIONS, 
                index=STATUS_OPTIONS.index(current_status),
                key=f"status_radio_{selected_id}",
                horizontal=True
            )
            if st.button("Update Status", type="primary", key=f"update_btn_{selected_id}"):
                result, success = update_visitor_status(selected_id, new_status)
                if success:
                    st.success(f"Status updated to '{result.get('status')}' for {selected_visitor['name']}.")
                    st.rerun()
                else:
                    st.error(f"Update failed: {result.get('detail', 'Unknown error')}")

        with col_delete:
            st.markdown("---")
            st.warning("⚠️ Deleting this record is permanent.")
            # Note: We don't use st.warning as a conditional button, just st.button
            if st.button("Delete Visitor Record", type="secondary", key=f"delete_btn_{selected_id}"):
                
                # Use a confirmation box before deleting
                if st.session_state.get('confirm_delete') != selected_id:
                    st.session_state['confirm_delete'] = selected_id
                    st.error("Click again to confirm PERMANENT deletion!")
                else:
                    result, success = delete_visitor(selected_id)
                    if success:
                        st.session_state['confirm_delete'] = None # Reset confirmation
                        st.success(f"Record for {selected_visitor['name']} deleted.")
                        st.rerun()
                    else:
                        st.error(f"Deletion failed: {result.get('detail', 'Unknown error')}")


def main():
    st.set_page_config(
        page_title="Visitor Parking Manager",
        page_icon="🚗",
        layout="wide"
    )
    
    st.title("Visitor Parking Management System (MongoDB + FastAPI + Streamlit)")
    st.markdown("Register, track, and manage all visitors using unique IC numbers and license plates.")

    # 1. Check API Connection
    if not check_api_connection():
        st.error("🛑 Cannot connect to FastAPI. Please ensure the backend is running on http://localhost:8002.")
        st.info("In Terminal 1: uvicorn api_task:app --reload --host 0.0.0.0 --port 8002")
        return
    
    st.success("Backend API Connected Successfully")

    # Load tasks first
    visitors, success = get_all_visitors()
    
    if not success:
        st.error("Failed to retrieve visitors from API.")
        return

    # Use tabs for organization
    tab_register, tab_view, tab_manage = st.tabs(["🚗 Register Visitor", "📋 View All Visitors", "⚙️ Manage Visitor"])
    
    with tab_register:
        create_visitor_form()

    with tab_view:
        st.header(f"All Registered Visitors ({len(visitors)})")
        display_visitor_table(visitors)
        
    with tab_manage:
        if visitors:
            manage_visitor_status_form(visitors)
        else:
            st.info("No visitors to manage yet. Please register one first.")

if __name__ == "__main__":
    main()


-----------------------------------------------------------------------

import streamlit as st
import requests
import pandas as pd
from typing import List, Dict, Any

# API is expected to run on port 8002
API_BASE_URL = "http://localhost:8002" 
STATUS_OPTIONS = ["Active", "Left"]

# --- API CLIENT FUNCTIONS ---

def check_api_connection():
    """Check if the FastAPI server is running and accessible."""
    try:
        # Check for 200 from the health check endpoint
        response = requests.get(f"{API_BASE_URL}/") 
        return response.status_code == 200
    except:
        return False
    
def get_all_visitors() -> List[Dict[str, Any]]:
    """Get all visitors via API."""
    try: 
        response = requests.get(f"{API_BASE_URL}/visitors/")
        if response.status_code == 200:
            return response.json(), True
        return [], False
    except:
        return [], False

def create_visitor(name: str, ic_number: str, license_plate: str, unit_number: str):
    """
    Register a new visitor via API. 
    Sends the four fields required by the VisitorCreate Pydantic model.
    """
    payload = {
        "name": name, 
        "IC_number": ic_number, 
        "license_plate": license_plate, 
        "unit_number": unit_number
    }
    try:
        response = requests.post(
            f"{API_BASE_URL}/visitors/",
            json=payload
        )
        # 201 Created is expected
        return response.json(), response.status_code == 201
    except Exception as e:
        return {"error": str(e)}, False

def update_visitor_status(visitor_id: str, new_status: str):
    """Update an existing visitor's status via API."""
    try:
        response = requests.put(
            f"{API_BASE_URL}/visitors/{visitor_id}/status",
            json={"status": new_status}
        )
        # 200 OK is expected
        return response.json(), response.status_code == 200
    except Exception as e:
        return {"error": str(e)}, False

def delete_visitor(visitor_id: str):
    """Delete a visitor record via API."""
    try: 
        response = requests.delete(f"{API_BASE_URL}/visitors/{visitor_id}")
        # 204 No Content is expected for successful delete
        return {}, response.status_code == 204
    except Exception as e:
        return {"error": str(e)}, False

# --- STREAMLIT PAGE FUNCTIONS (Build the UI) ---
    
def display_visitor_table(visitors: List[Dict[str, Any]]):
    """Displays all visitors in a styled table format."""
    
    if not visitors:
        st.info("No visitors registered yet.")
        return
        
    # Convert list of dicts to DataFrame for better display
    df = pd.DataFrame(visitors)
    
    # Rename columns for display
    df = df.rename(columns={
        'id': 'ID', 
        'name': 'Visitor Name', 
        'IC_number': 'IC Number', 
        'license_plate': 'License Plate', 
        'unit_number': 'Unit No.', 
        'status': 'Status',
        'registered_at': 'Registered At'
    })

    # Prepare data for display
    # The datetime field is now an ISO string, so we just convert it to datetime object for formatting
    df['Registered At'] = pd.to_datetime(df['Registered At']).dt.strftime('%Y-%m-%d %H:%M')
    df['ID'] = df['ID'].str[:8] + '...' # Truncate ID for readability

    
    st.dataframe(
        df[['ID', 'Visitor Name', 'IC Number', 'License Plate', 'Unit No.', 'Status', 'Registered At']],
        hide_index=True,
        width=True,
        column_config={
            "Status": st.column_config.TextColumn("Status", help="Current visitor status", width="small")
        }
    )

def create_visitor_form():
    """Form to register a new visitor."""
    st.header("Register New Visitor")
    
    with st.form("create_visitor_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Visitor Name")
            license_plate = st.text_input("License Plate (Unique)", placeholder="e.g., JAA1234")
        with col2:
            ic_number = st.text_input("IC Number (Unique)", placeholder="e.g., 901231-14-5678")
            unit_number = st.text_input("Unit Number Visiting", placeholder="e.g., B-1-01")

        submitted = st.form_submit_button("Register Visitor", type="primary")

        if submitted:
            if all([name, ic_number, license_plate, unit_number]):
                result, success = create_visitor(name, ic_number, license_plate, unit_number)
                if success:
                    st.success(f"Visitor '{result.get('name')}' registered successfully with ID: {result.get('id')[:8]}...")
                    st.toast("Registration Complete!", icon="🎉")
                    st.rerun()
                else:
                    st.error(f"Registration failed: {result.get('detail', 'Unknown API error')}")
            else:
                st.error("All fields are required.")

def manage_visitor_status_form(visitors: List[Dict[str, Any]]):
    """Interface to update status or delete a visitor."""
    st.header("Manage Visitor Status & Deletion")

    # Create selection dictionary for dropdown
    options = {
        f"{v['name']} ({v['license_plate']}) - ID: {v['id'][:8]}..." : v['id']
        for v in visitors
    }
    
    selected_display = st.selectbox(
        "Select Visitor to Manage",
        options=list(options.keys()),
        index=None
    )

    if selected_display:
        selected_id = options[selected_display]
        selected_visitor = next(v for v in visitors if v['id'] == selected_id)
        current_status = selected_visitor['status']

        st.markdown(f"**Current Status:** :blue[{current_status}]")
        
        col_status, col_delete = st.columns(2)

        with col_status:
            # Use a slightly different key for the radio button to prevent clashes
            new_status = st.radio(
                "Change Status To:", 
                options=STATUS_OPTIONS, 
                index=STATUS_OPTIONS.index(current_status),
                key=f"status_radio_{selected_id}",
                horizontal=True
            )
            if st.button("Update Status", type="primary", key=f"update_btn_{selected_id}"):
                result, success = update_visitor_status(selected_id, new_status)
                if success:
                    st.success(f"Status updated to '{result.get('status')}' for {selected_visitor['name']}.")
                    st.rerun()
                else:
                    st.error(f"Update failed: {result.get('detail', 'Unknown error')}")

        with col_delete:
            st.markdown("---")
            st.warning("⚠️ Deleting this record is permanent.")
            # Note: We don't use st.warning as a conditional button, just st.button
            if st.button("Delete Visitor Record", type="secondary", key=f"delete_btn_{selected_id}"):
                
                # Use a confirmation box before deleting
                if st.session_state.get('confirm_delete') != selected_id:
                    st.session_state['confirm_delete'] = selected_id
                    st.error("Click again to confirm PERMANENT deletion!")
                else:
                    result, success = delete_visitor(selected_id)
                    if success:
                        st.session_state['confirm_delete'] = None # Reset confirmation
                        st.success(f"Record for {selected_visitor['name']} deleted.")
                        st.rerun()
                    else:
                        st.error(f"Deletion failed: {result.get('detail', 'Unknown error')}")


def main():
    st.set_page_config(
        page_title="Visitor Parking Manager",
        page_icon="🚗",
        layout="wide"
    )
    
    st.title("Visitor Parking Management System (MongoDB + FastAPI + Streamlit)")
    st.markdown("Register, track, and manage all visitors using unique IC numbers and license plates.")

    # 1. Check API Connection
    if not check_api_connection():
        st.error("🛑 Cannot connect to FastAPI. Please ensure the backend is running on http://localhost:8002.")
        st.info("In Terminal 1: uvicorn api_task:app --reload --host 0.0.0.0 --port 8002")
        return
    
    st.success("Backend API Connected Successfully")

    # Load tasks first
    visitors, success = get_all_visitors()
    
    if not success:
        st.error("Failed to retrieve visitors from API.")
        return

    # Use tabs for organization
    tab_register, tab_view, tab_manage = st.tabs(["🚗 Register Visitor", "📋 View All Visitors", "⚙️ Manage Visitor"])
    
    with tab_register:
        create_visitor_form()

    with tab_view:
        st.header(f"All Registered Visitors ({len(visitors)})")
        display_visitor_table(visitors)
        
    with tab_manage:
        if visitors:
            manage_visitor_status_form(visitors)
        else:
            st.info("No visitors to manage yet. Please register one first.")

if __name__ == "__main__":
    main()
