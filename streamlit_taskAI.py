import streamlit as st
import requests
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
import time
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re

if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 5  # Refresh every 5 second

API_BASE_URL = "http://localhost:8000" 
STATUS_OPTIONS = ["active", "left"]  
TOTAL_PARKING_SPOTS = 200

# Optional: Set Tesseract path (uncomment and modify if needed)
# For Windows: pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# For Mac (if not in PATH): pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'

def extract_license_plate(image):
    """Extract license plate text from uploaded image using OCR."""
    try:
        # Convert PIL image to numpy array for OpenCV
        img_array = np.array(image)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Apply preprocessing to improve OCR accuracy
        # 1. Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # 2. Increase contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        contrast = clahe.apply(denoised)
        
        # 3. Apply threshold
        _, thresh = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Use Tesseract to extract text
        # Config for license plates (alphanumeric, limited characters)
        custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        text = pytesseract.image_to_string(thresh, config=custom_config)
        
        # Clean up the extracted text
        plate_text = text.strip().upper()
        # Remove spaces and special characters
        plate_text = re.sub(r'[^A-Z0-9]', '', plate_text)
        
        return plate_text if plate_text else None
        
    except Exception as e:
        st.error(f"OCR Error: {str(e)}")
        return None

def check_api_connection():
    """Check if the FastAPI server is running and accessible."""
    try:
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
        "ic_number": ic_number, 
        "license_plate": license_plate, 
        "unit_number": unit_number
    }
    try:
        response = requests.post(
            f"{API_BASE_URL}/visitors/",
            json=payload
        )
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
        return response.json(), response.status_code == 200
    except Exception as e:
        return {"error": str(e)}, False

def edit_visitor(visitor_id: str, name: str, ic_number: str, license_plate: str, unit_number: str):
    """Update visitor details via API."""
    payload = {
        "name": name,
        "ic_number": ic_number,
        "license_plate": license_plate,
        "unit_number": unit_number
    }
    try:
        response = requests.put(
            f"{API_BASE_URL}/visitors/{visitor_id}",
            json=payload
        )
        if response.status_code == 200:
            return response.json(), True
        else:
            return response.json(), False
    except Exception as e:
        return {"error": str(e)}, False

def delete_visitor(visitor_id: str):
    """Delete a visitor record via API."""
    try: 
        response = requests.delete(f"{API_BASE_URL}/visitors/{visitor_id}")
        return {}, response.status_code == 204
    except Exception as e:
        return {"error": str(e)}, False

# --- STREAMLIT PAGE FUNCTIONS (Build the UI) ---

def display_dashboard(visitors: List[Dict[str, Any]]):
    """Display parking availability dashboard with charts and stats."""
    
    col_header, col_refresh = st.columns([4, 1])
    with col_header:
        st.header("📊 Parking Dashboard")
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_dashboard"):
            st.rerun()
    
    # Calculate statistics - case insensitive status check
    total_visitors = len(visitors)
    active_visitors = len([v for v in visitors if v['status'].lower() == 'active'])
    left_visitors = len([v for v in visitors if v['status'].lower() == 'left'])
    available_spots = TOTAL_PARKING_SPOTS - active_visitors
    occupancy_rate = (active_visitors / TOTAL_PARKING_SPOTS * 100) if TOTAL_PARKING_SPOTS > 0 else 0
    
    # Top metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🚗 Occupied Spots",
            value=active_visitors,
            delta=f"{occupancy_rate:.1f}% full"
        )
    
    with col2:
        st.metric(
            label="✅ Available Spots",
            value=available_spots,
            delta=f"{(available_spots/TOTAL_PARKING_SPOTS*100):.1f}% free"
        )
    
    with col3:
        st.metric(
            label="📋 Total Capacity",
            value=TOTAL_PARKING_SPOTS
        )
    
    with col4:
        st.metric(
            label="👋 Visitors Left",
            value=left_visitors
        )
    
    st.divider()

    
    # Visual charts
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Parking Occupancy")
        
        # Create data for pie chart
        occupancy_data = pd.DataFrame({
            'Status': ['Occupied', 'Available'],
            'Count': [active_visitors, available_spots]
        })
        
        # Color coding
        colors = ["#FF6B6B", "#51CF66"]
        
        import plotly.graph_objects as go
        
        fig = go.Figure(data=[go.Pie(
            labels=occupancy_data['Status'],
            values=occupancy_data['Count'],
            hole=0.4,
            marker_colors=colors,
            textinfo='label+value+percent',
            textfont_size=14
        )])
        
        fig.update_layout(
            showlegend=True,
            height=400,
            margin=dict(t=20, b=20, l=20, r=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col_chart2:
        st.subheader("Visitor Status Breakdown")
        
        # Bar chart data
        status_data = pd.DataFrame({
            'Status': ['Active (Parked)', 'Left', 'Available Spots'],
            'Count': [active_visitors, left_visitors, available_spots],
            'Color': ["#FF6B6B", "#EBA254", "#51CF66"]
        })
        
        # Create bar chart
        fig2 = go.Figure(data=[
            go.Bar(
                x=status_data['Status'],
                y=status_data['Count'],
                marker_color=status_data['Color'],
                text=status_data['Count'],
                textposition='auto',
            )
        ])
        
        fig2.update_layout(
            yaxis_title="Number of Spots",
            showlegend=False,
            height=400,
            margin=dict(t=20, b=20, l=20, r=20)
        )
        
        st.plotly_chart(fig2, use_container_width=True)
    
    st.divider()

    # Parking status indicator
    if available_spots == 0:
        st.error("🚫 PARKING FULL - No spots available!")
    elif available_spots < 20:
        st.warning(f"⚠️ Low availability - Only {available_spots} spots remaining!")
    else:
        st.success(f"✅ Parking available - {available_spots} spots free!")
    
    
def display_visitor_table(visitors: List[Dict[str, Any]]):
    """Displays all visitors in a styled table format."""
    
    if not visitors:
        st.info("No visitors registered yet.")
        return
        
    # Convert list of dicts to DataFrame for better display
    df = pd.DataFrame(visitors)
    
    # Handle both 'id' and '_id' field names from API
    id_field = 'id' if 'id' in df.columns else '_id'
    
    # Rename columns for display
    column_mapping = {
        id_field: 'ID', 
        'name': 'Visitor Name', 
        'ic_number': 'IC Number', 
        'license_plate': 'License Plate', 
        'unit_number': 'Unit No.', 
        'status': 'Status',
        'created_at': 'Registered At'
    }
    
    # Only rename columns that exist
    rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    # Format datetime if the column exists
    if 'Registered At' in df.columns:
        try:
            df['Registered At'] = df['Registered At'].astype(str)
            df['Registered At'] = pd.to_datetime(
                df['Registered At'],
                format='mixed',
                utc=True
            )
            df['Registered At'] = df['Registered At'].dt.tz_localize(None)
            df['Registered At'] = df['Registered At'].dt.strftime('%Y-%m-%d %H:%M')
        except Exception as e:
            st.warning(f"Error formatting dates: {e}")
            df['Registered At'] = df['Registered At'].astype(str)
    
    # Truncate ID for display
    if 'ID' in df.columns:
        df['ID'] = df['ID'].str[:8] + '...'

    # Select and order columns
    display_columns = [col for col in [
        'ID', 'Visitor Name', 'IC Number', 
        'License Plate', 'Unit No.', 'Status', 
        'Registered At'
    ] if col in df.columns]
    
    # Display the dataframe
    st.dataframe(
        df[display_columns],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Status": st.column_config.TextColumn(
                "Status", 
                help="Current visitor status", 
                width="small"
            )
        }
    )

def create_visitor_form():
    """Form to register a new visitor."""
    st.header("🚗 Register New Visitor")
    
    # License Plate OCR Section
    st.subheader("📸 AI License Plate Scanner")
    
    col_upload, col_preview = st.columns([1, 1])
    
    with col_upload:
        uploaded_file = st.file_uploader(
            "Upload License Plate Image (Optional)",
            type=["jpg", "jpeg", "png"],
            help="Upload a photo of the license plate for automatic recognition"
        )
        
        if uploaded_file is not None:
            # Display the uploaded image
            image = Image.open(uploaded_file)
            
            with col_preview:
                st.image(image, caption="Uploaded Image", use_container_width=True)
            
            # Extract license plate button
            if st.button("🤖 Scan License Plate", type="secondary"):
                with st.spinner("🔍 AI is reading the license plate..."):
                    plate_number = extract_license_plate(image)
                    
                    if plate_number:
                        st.success(f"✅ Detected: **{plate_number}**")
                        # Store in session state to auto-fill
                        st.session_state.detected_plate = plate_number
                    else:
                        st.error("❌ Could not detect license plate. Please enter manually.")
                        st.session_state.detected_plate = ""
    
    st.divider()
    
    # Registration form
    with st.form("create_visitor_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Visitor Name")
            # Auto-fill if OCR detected a plate
            default_plate = st.session_state.get('detected_plate', '')
            license_plate = st.text_input(
                "License Plate (Unique)", 
                value=default_plate,
                placeholder="e.g., JOM1234"
            )
        with col2:
            ic_number = st.text_input("IC Number (Unique)", placeholder="e.g., 901231-14-5678")
            unit_number = st.text_input("Unit Number Visiting", placeholder="e.g., B-1-01")

        submitted = st.form_submit_button("Register Visitor", type="primary")

        if submitted:
            if all([name, ic_number, license_plate, unit_number]):
                result, success = create_visitor(name, ic_number, license_plate, unit_number)
                if success:
                    st.success(f"Visitor registered successfully! ID: {result.get('visitor_id')[:8]}...")
                    st.toast("Registration Complete!", icon="🎉")
                    # Clear the detected plate from session
                    if 'detected_plate' in st.session_state:
                        del st.session_state.detected_plate
                    st.rerun()
                else:
                    st.error(f"Registration failed: {result.get('detail', 'Unknown API error')}")
            else:
                st.error("All fields are required.")

def edit_and_manage_visitor_form(visitors: List[Dict[str, Any]]):
    """Combined interface to edit, update status, or delete visitors with card-style UI."""
    st.header("⚙️ Edit & Manage Visitors")
    
    # Handle both 'id' and '_id' field names
    id_field = 'id' if 'id' in visitors[0] else '_id'
    
    # Display visitors in expandable cards
    for visitor in visitors:
        visitor_id = visitor[id_field]
        
        # Create an expander for each visitor (card-style)
        with st.expander(
            f"🚗 {visitor['name']} | {visitor['license_plate']} | Status: {visitor['status'].capitalize()}",
            expanded=False
        ):
            # Show visitor details
            col_info1, col_info2 = st.columns(2)
            
            with col_info1:
                st.markdown(f"**👤 Name:** {visitor['name']}")
                st.markdown(f"**🪪 IC Number:** {visitor['ic_number']}")
            
            with col_info2:
                st.markdown(f"**🚘 License Plate:** {visitor['license_plate']}")
                st.markdown(f"**🏠 Unit Number:** {visitor['unit_number']}")
            
            st.markdown(f"**📊 Status:** :blue[{visitor['status'].capitalize()}]")
            st.markdown(f"**🕐 Registered:** {visitor.get('registered_at', 'N/A')}")
            
            st.divider()
            
            # Create tabs within each card for Edit/Status/Delete
            tab_edit, tab_status, tab_delete = st.tabs(["✏️ Edit Details", "🔄 Change Status", "🗑️ Delete"])
            
            with tab_edit:
                with st.form(f"edit_form_{visitor_id}"):
                    st.markdown("##### Edit Visitor Information")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_name = st.text_input("Name", value=visitor['name'], key=f"name_{visitor_id}")
                        new_plate = st.text_input("License Plate", value=visitor['license_plate'], key=f"plate_{visitor_id}")
                    
                    with col2:
                        new_ic = st.text_input("IC Number", value=visitor['ic_number'], key=f"ic_{visitor_id}")
                        new_unit = st.text_input("Unit Number", value=visitor['unit_number'], key=f"unit_{visitor_id}")
                    
                    submit_edit = st.form_submit_button("💾 Save Changes", type="primary")
                    
                    if submit_edit:
                        if all([new_name, new_ic, new_plate, new_unit]):
                            result, success = edit_visitor(visitor_id, new_name, new_ic, new_plate, new_unit)
                            if success:
                                st.success("✅ Details updated successfully!")
                                st.rerun()
                            else:
                                st.error(f"❌ Update failed: {result.get('detail', 'Unknown error')}")
                        else:
                            st.error("All fields are required.")
            
            with tab_status:
                st.markdown("##### Change Visitor Status")
                current_status = visitor['status'].lower()
                
                col_status1, col_status2 = st.columns([2, 1])
                
                with col_status1:
                    new_status = st.radio(
                        "Select new status:",
                        options=STATUS_OPTIONS,
                        format_func=str.capitalize,
                        index=STATUS_OPTIONS.index(current_status),
                        key=f"status_{visitor_id}",
                        horizontal=True
                    )
                
                with col_status2:
                    if st.button("🔄 Update Status", key=f"update_status_{visitor_id}", type="primary"):
                        result, success = update_visitor_status(visitor_id, new_status)
                        if success:
                            st.success(f"✅ Status updated to '{new_status.capitalize()}'")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed: {result.get('detail', 'Unknown error')}")
            
            with tab_delete:
                st.markdown("##### Delete Visitor Record")
                st.warning("⚠️ **Warning:** This action is permanent and cannot be undone!")
                
                col_del1, col_del2, col_del3 = st.columns([1, 1, 2])
                
                with col_del1:
                    if st.button("🗑️ Delete", key=f"delete_{visitor_id}", type="secondary"):
                        if st.session_state.get('confirm_delete') != visitor_id:
                            st.session_state['confirm_delete'] = visitor_id
                
                with col_del2:
                    if st.session_state.get('confirm_delete') == visitor_id:
                        if st.button("✅ Confirm Delete", key=f"confirm_delete_{visitor_id}", type="primary"):
                            result, success = delete_visitor(visitor_id)
                            if success:
                                st.session_state['confirm_delete'] = None
                                st.success("✅ Visitor deleted successfully!")
                                st.rerun()
                            else:
                                st.error(f"❌ Failed: {result.get('detail', 'Unknown error')}")
                
                with col_del3:
                    if st.session_state.get('confirm_delete') == visitor_id:
                        st.error("👈 Click 'Confirm Delete' to proceed")


def main():
    st.set_page_config(
        page_title=" Parking Manager",
        page_icon="🚗",
        layout="wide"
    )
    
    st.title("🚗  Parking Management System")
    st.markdown("🛡️ Register, track, and manage all visitors.🛡️")

    # 1. Check API Connection
    if not check_api_connection():
        st.error("🛑 Cannot connect to FastAPI. Please ensure the backend is running on http://localhost:8002.")
        st.info("Run: python api_task.py")
        return
    
    st.success("✅ WELCOME! CONNECTED TO FASTAPI.")

    # Load visitors first
    visitors, success = get_all_visitors()
    
    if not success:
        st.error("Failed to retrieve visitors from API.")
        return

    # Update tabs
    tab_register, tab_dashboard, tab_view, tab_manage = st.tabs([
        "🚗 Register Visitor", 
        "📊 Dashboard", 
        "📋 View All Visitors",
        "⚙️ Edit & Manage"
    ])
    
    with tab_dashboard:
        display_dashboard(visitors)

    with tab_register:
        create_visitor_form()

    with tab_view:
        st.header(f"📋 All Registered Visitors ({len(visitors)})")
        display_visitor_table(visitors)
            
    with tab_manage:
        if visitors:
            edit_and_manage_visitor_form(visitors)
        else:
            st.info("No visitors to manage yet. Please register one first.")

if __name__ == "__main__":
    main()