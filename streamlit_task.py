import streamlit as st
import requests
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
import time

if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 5  # Refresh every 5 second

API_BASE_URL = "http://localhost:8002" 
STATUS_OPTIONS = ["active", "left"]  
TOTAL_PARKING_SPOTS = 200

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
        colors = ["#FF6B6B", "#51CF66"]  # Red for occupied, Green for available
        
        # Display pie chart using Streamlit's native chart
        fig_data = occupancy_data.set_index('Status')
        
        # Use Plotly-style pie chart if available, otherwise use bar
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
            # First ensure the column is string type
            df['Registered At'] = df['Registered At'].astype(str)
            
            # Convert to datetime, handling various formats
            df['Registered At'] = pd.to_datetime(
                df['Registered At'],
                format='mixed',
                utc=True
            )
            
            # Convert to local time and format
            df['Registered At'] = df['Registered At'].dt.tz_localize(None)
            df['Registered At'] = df['Registered At'].dt.strftime('%Y-%m-%d %H:%M')
        except Exception as e:
            st.warning(f"Error formatting dates: {e}")
            # Fallback to raw string display
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
    
    with st.form("create_visitor_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Visitor Name")
            license_plate = st.text_input("License Plate (Unique)", placeholder="e.g., JOM1234")
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
                    st.rerun()
                else:
                    st.error(f"Registration failed: {result.get('detail', 'Unknown API error')}")
            else:
                st.error("All fields are required.")

def manage_visitor_status_form(visitors: List[Dict[str, Any]]):
    """Interface to update status or delete a visitor."""
    st.header("⚙️ Manage Visitor Status & Deletion")

    # Handle both 'id' and '_id' field names
    id_field = 'id' if 'id' in visitors[0] else '_id'
    
    # Create selection dictionary for dropdown
    options = {
        f"{v['name']} ({v['license_plate']}) - ID: {v[id_field][:8]}..." : v[id_field]
        for v in visitors
    }
    
    selected_display = st.selectbox(
        "Select Visitor to Manage",
        options=list(options.keys()),
        index=None
    )

    if selected_display:
        selected_id = options[selected_display]
        selected_visitor = next(v for v in visitors if v[id_field] == selected_id)
        current_status = selected_visitor['status'].lower()  # Ensure lowercase

        st.markdown(f"**Current Status:** :blue[{current_status.capitalize()}]")
        
        col_status, col_delete = st.columns(2)

        with col_status:
            new_status = st.radio(
                "Change Status To:", 
                options=STATUS_OPTIONS,
                format_func=str.capitalize,  
                index=STATUS_OPTIONS.index(current_status),
                key=f"status_radio_{selected_id}",
                horizontal=True
            )
            if st.button("Update Status", type="primary", key=f"update_btn_{selected_id}"):
                result, success = update_visitor_status(selected_id, new_status)
                if success:
                    st.success(f"Status updated to '{new_status}' for {selected_visitor['name']}.")
                    st.rerun()
                else:
                    st.error(f"Update failed: {result.get('detail', 'Unknown error')}")

        with col_delete:
            st.markdown("---")
            st.warning("⚠️ Deleting this record is permanent.")
            if st.button("Delete Visitor Record", type="secondary", key=f"delete_btn_{selected_id}"):
                
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
        page_title=" Parking Manager",
        page_icon="🚗",
        layout="wide"
    )
    
    st.title("🚗  Parking Management System")
    st.markdown("🛡️ Register, track, and manage all visitors.🛡️")

     # Load visitors with refresh handling
    current_time = time.time()
    if ('visitors' not in st.session_state or 
        current_time - st.session_state.last_refresh > st.session_state.refresh_interval):
        visitors, success = get_all_visitors()
        if success:
            st.session_state.visitors = visitors
            st.session_state.last_refresh = current_time
    else:
        visitors = st.session_state.visitors
        success = True

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

    # Use tabs for organization
    tab_register, tab_dashboard, tab_view, tab_manage = st.tabs(["🚗 Register Visitor", "📊 Dashboard", "📋 View All Visitors", "⚙️ Manage Visitor"])
    
    with tab_dashboard:
        display_dashboard(visitors)

    with tab_register:
        create_visitor_form()

    with tab_view:
        st.header(f"📋 All Registered Visitors ({len(visitors)})")
        display_visitor_table(visitors)
        
    with tab_manage:
        if visitors:
            manage_visitor_status_form(visitors)
        else:
            st.info("No visitors to manage yet. Please register one first.")

    

if __name__ == "__main__":
    main()