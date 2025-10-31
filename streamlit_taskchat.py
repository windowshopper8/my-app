import streamlit as st
import requests
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
import time
import os
from dotenv import load_dotenv
from chatbot import get_chatbot


#  Updated Chatbot imports for LangChain v0.1+
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pymongo import MongoClient

load_dotenv()

if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 5  # Refresh every 5 second

API_BASE_URL = "http://localhost:8000" 
STATUS_OPTIONS = ["active", "left"]  
TOTAL_PARKING_SPOTS = 105

# Initialize Gemini LLM for chatbot
try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.2
    )
except:
    llm = None  # Chatbot will be disabled if API key not found

def check_api_connection():
    """Check if the FastAPI server is running and accessible."""
    try:
        response = requests.get(f"{API_BASE_URL}/") 
        return response.status_code == 200
    except:
        return False
    
def search_and_filter_visitors(visitors: List[Dict[str, Any]], 
                                 search_query: str = "", 
                                 status_filter: str = "All",
                                 unit_filter: str = "All",
                                 date_from = None,
                                 date_to = None) -> List[Dict[str, Any]]:
    """
    Filter visitors based on search query and filters.
    """
    if not visitors:
        return []
    
    filtered = visitors.copy()
    
    # Search by name, IC, or license plate
    if search_query:
        search_query = search_query.lower()
        filtered = [
            v for v in filtered
            if search_query in v.get('name', '').lower() or
               search_query in v.get('ic_number', '').lower() or
               search_query in v.get('license_plate', '').lower()
        ]
    
    # Filter by status
    if status_filter != "All":
        filtered = [v for v in filtered if v.get('status', '').lower() == status_filter.lower()]
    
    # Filter by unit
    if unit_filter != "All":
        filtered = [v for v in filtered if v.get('unit_number', '') == unit_filter]
    
    # Filter by date range
    if date_from or date_to:
        date_filtered = []
        for v in filtered:
            try:
                # Handle both string and datetime objects
                reg_datetime = v.get('created_at')
                if isinstance(reg_datetime, str):
                    reg_date = pd.to_datetime(reg_datetime).date()
                else:
                    reg_date = pd.to_datetime(reg_datetime).date()
                
                # Check date range
                include = True
                if date_from and date_to:
                    # Both dates selected
                    if not (date_from <= reg_date <= date_to):
                        include = False
                elif date_from:
                    # Only from date
                    if reg_date < date_from:
                        include = False
                elif date_to:
                    # Only to date
                    if reg_date > date_to:
                        include = False
                
                if include:
                    date_filtered.append(v)
            except Exception as e:
                # If date parsing fails, skip this visitor
                continue
        filtered = date_filtered
    
    return filtered


def display_search_filters(visitors: List[Dict[str, Any]]):
    """
    Display search and filter controls.
    Returns filtered visitor list.
    """
    st.subheader("🔍 Search & Filter")
    
    # Get unique units for filter
    unique_units = sorted(list(set([v.get('unit_number', '') for v in visitors if v.get('unit_number')])))
    
    # Search bar
    col_search, col_status, col_unit = st.columns([2, 1, 1])
    
    with col_search:
        search_query = st.text_input(
            "🔎 Search",
            placeholder="Search by name, IC, or license plate...",
            key="search_visitors"
        )
    
    with col_status:
        status_filter = st.selectbox(
            "Status",
            options=["All", "Active", "Left"],
            key="status_filter"
        )
    
    with col_unit:
        unit_options = ["All"] + unique_units
        unit_filter = st.selectbox(
            "Unit Number",
            options=unit_options,
            key="unit_filter"
        )
    
    # Date range filter (expandable)
    with st.expander("📅 Filter by Date Range"):
        col_date1, col_date2 = st.columns(2)
        
        with col_date1:
            date_from = st.date_input(
                "From Date",
                value=None,
                key="date_from"
            )
        
        with col_date2:
            date_to = st.date_input(
                "To Date",
                value=None,
                key="date_to"
            )
    
    # Apply filters
    filtered_visitors = search_and_filter_visitors(
        visitors,
        search_query,
        status_filter,
        unit_filter,
        date_from,
        date_to
    )
    
    # Show filter results count
    if len(filtered_visitors) != len(visitors):
        st.info(f"📊 Showing {len(filtered_visitors)} of {len(visitors)} visitors")
    
    return filtered_visitors

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

# --- STREAMLIT PAGE FUNCTIONS (UI) ---

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

# 🆕 NEW: Chatbot display function
def display_chatbot():
    """Display the AI chatbot interface."""
    st.header("🤖 AI Parking Assistant")
    
    # Get chatbot instance
    bot = get_chatbot()
    
    if not bot.is_available:
        st.error("⚠️ Chatbot unavailable. Please add GOOGLE_API_KEY to your .env file.")
        st.info("Get your API key from: https://makersuite.google.com/app/apikey")
        return
    
    st.markdown("""
    💬 **Ask me anything about parking visitors!**
    """)
    
    # Initialize chat history in session state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about parking visitors..."):
        # Add user message to history
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get and display chatbot response
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                try:
                    response = bot.get_response(prompt)
                    st.markdown(response)
                    st.session_state.chat_messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    error_msg = f"Sorry, I encountered an error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})
    
    # 🔧 CHANGE: Enhanced quick action buttons with more options
    st.divider()
    st.markdown("**💡 Quick Questions:**")
    
    # Define preset questions
    quick_questions = [
        ("📊 How many spots are available?", "How many visitors are currently parked and how many spots are available?"),
        ("📋 Can you list all visitors?", "Show me all visitors"),
        ("🔍 How can I search for visitors?", "How can I search for specific visitors by name or license plate?"),
        ("🏢 How to find visitors by unit?", "How can I find all visitors for a specific unit number?"),
        ("🟢 Who are the active visitors?", "Show me all active visitors currently parked"),
        ("🆘 What can you help with?", "What can you help me with?")
    ]
    
    # Display buttons in 3 columns, 2 rows
    col1, col2, col3 = st.columns(3)
    
    for i, (label, question) in enumerate(quick_questions):
        col = [col1, col2, col3][i % 3]
        
        with col:
            if st.button(label, key=f"quick_{i}", use_container_width=True):
                # Add to chat history
                st.session_state.chat_messages.append({"role": "user", "content": question})
                
                # Get response
                with st.spinner("Getting answer..."):
                    response = bot.get_response(question)
                    st.session_state.chat_messages.append({"role": "assistant", "content": response})
                
                st.rerun()
    
    st.divider()
    
    # Clear chat button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_messages = []
        st.rerun()
def display_visitor_table(visitors: List[Dict[str, Any]], show_filters: bool = True):
    """Displays all visitors in a styled table format."""
    
    if not visitors:
        st.info("No visitors registered yet.")
        return
    
    # Add search and filters
    if show_filters:
        filtered_visitors = display_search_filters(visitors)
    else:
        filtered_visitors = visitors
    
    if not filtered_visitors:
        st.warning("No visitors match your search criteria.")
        return
        
    # Convert list of dicts to DataFrame for better display
    df = pd.DataFrame(filtered_visitors)
    
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
    st.header("👥 Register New Visitor")
    
    with st.form("create_visitor_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Visitor Name")
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
                    if 'detected_plate' in st.session_state:
                        del st.session_state.detected_plate
                    st.rerun()
                else:
                    st.error(f"Registration failed: {result.get('detail', 'Unknown API error')}")
            else:
                st.error("All fields are required.")

def edit_and_manage_visitor_form(visitors: List[Dict[str, Any]]):
    """Combined interface to edit, update status, or delete visitors with card-style UI and search."""
    st.header("⚙️ Edit & Manage Visitors")
    
    if not visitors:
        st.info("No visitors to manage yet. Please register one first.")
        return
    
    # Handle both 'id' and '_id' field names
    id_field = 'id' if 'id' in visitors[0] else '_id'
    
    # 🆕 FIXED: Properly aligned search section
    st.markdown("### 🔍 Search Visitors")
    
    # Search input (full width)
    search_query = st.text_input(
        "Search by name, IC number, license plate, or unit number",
        placeholder="Type to search...",
        key="manage_search",
        label_visibility="collapsed"
    )
    
    # 🔧 CHANGE: Filter and Sort in same row below search
    col_filter, col_sort = st.columns(2)
    
    with col_filter:
        search_status = st.selectbox(
            "Filter by status",
            options=["All", "Active", "Left"],
            key="manage_status_filter"
        )
    
    with col_sort:
        sort_by = st.selectbox(
            "Sort by",
            options=["Recent First", "Name (A-Z)", "Name (Z-A)", "Unit Number"],
            key="manage_sort"
        )
    
    # Filter visitors based on search
    filtered_visitors = visitors.copy()
    
    # Apply search filter
    if search_query:
        search_lower = search_query.lower()
        filtered_visitors = [
            v for v in filtered_visitors
            if search_lower in v.get('name', '').lower() or
               search_lower in v.get('ic_number', '').lower() or
               search_lower in v.get('license_plate', '').lower() or
               search_lower in v.get('unit_number', '').lower()
        ]
    
    # Apply status filter
    if search_status != "All":
        filtered_visitors = [
            v for v in filtered_visitors
            if v.get('status', '').lower() == search_status.lower()
        ]
    
    # Apply sorting
    if sort_by == "Recent First":
        pass  # Already sorted by default
    elif sort_by == "Name (A-Z)":
        filtered_visitors = sorted(filtered_visitors, key=lambda x: x.get('name', '').lower())
    elif sort_by == "Name (Z-A)":
        filtered_visitors = sorted(filtered_visitors, key=lambda x: x.get('name', '').lower(), reverse=True)
    elif sort_by == "Unit Number":
        filtered_visitors = sorted(filtered_visitors, key=lambda x: x.get('unit_number', ''))
    
    # Show search results count
    if search_query or search_status != "All":
        if len(filtered_visitors) == 0:
            st.warning(f"🔍 No visitors found matching '{search_query}'")
            st.info("💡 **Search Tips:**\n- Try searching by partial name\n- Check the spelling\n- Try searching by license plate or unit number")
            return
        else:
            st.success(f"✅ Found {len(filtered_visitors)} visitor(s) matching your search")
    else:
        st.info(f"📊 Showing all {len(filtered_visitors)} visitors")
    
    st.markdown(f"### Visitors ({len(filtered_visitors)})")
    
    # Display visitors in expandable cards
    for visitor in filtered_visitors:
        visitor_id = visitor[id_field]
        
        card_title = f"🚗 {visitor['name']} | {visitor['license_plate']} | Unit: {visitor['unit_number']} | Status: {visitor['status'].capitalize()}"
        status_emoji = "🟢" if visitor['status'].lower() == 'active' else "🔴"
        
        with st.expander(f"{status_emoji} {card_title}", expanded=False):
            # Show visitor details
            col_info1, col_info2 = st.columns(2)
            
            with col_info1:
                st.markdown(f"**👤 Name:** {visitor['name']}")
                st.markdown(f"**🪪 IC Number:** {visitor.get('ic_number', 'N/A')}")
            
            with col_info2:
                st.markdown(f"**🚘 License Plate:** {visitor['license_plate']}")
                st.markdown(f"**🏠 Unit Number:** {visitor['unit_number']}")
            
            st.markdown(f"**📊 Status:** :{'green' if visitor['status'].lower() == 'active' else 'red'}[{visitor['status'].capitalize()}]")
            
            # Better date formatting
            created_at = visitor.get('created_at', 'N/A')
            if created_at != 'N/A':
                try:
                    if isinstance(created_at, str):
                        created_date = pd.to_datetime(created_at)
                    else:
                        created_date = created_at
                    formatted_date = created_date.strftime('%B %d, %Y at %H:%M')
                    st.markdown(f"**🕐 Registered:** {formatted_date}")
                except:
                    st.markdown(f"**🕐 Registered:** {created_at}")
            else:
                st.markdown(f"**🕐 Registered:** N/A")
            
            st.divider()
            
            # Create tabs within each card
            tab_edit, tab_status, tab_delete = st.tabs(["✏️ Edit Details", "🔄 Change Status", "🗑️ Delete"])
            
            with tab_edit:
                with st.form(f"edit_form_{visitor_id}"):
                    st.markdown("##### Edit Visitor Information")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_name = st.text_input("Name", value=visitor['name'], key=f"name_{visitor_id}")
                        new_plate = st.text_input("License Plate", value=visitor['license_plate'], key=f"plate_{visitor_id}")
                    
                    with col2:
                        new_ic = st.text_input("IC Number", value=visitor.get('ic_number', ''), key=f"ic_{visitor_id}")
                        new_unit = st.text_input("Unit Number", value=visitor['unit_number'], key=f"unit_{visitor_id}")
                    
                    submit_edit = st.form_submit_button("💾 Save Changes", type="primary")
                    
                    if submit_edit:
                        if all([new_name, new_ic, new_plate, new_unit]):
                            result, success = edit_visitor(visitor_id, new_name, new_ic, new_plate, new_unit)
                            if success:
                                st.success("✅ Details updated successfully!")
                                st.toast(f"Updated {new_name}'s information", icon="✅")
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
                        index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0,
                        key=f"status_{visitor_id}",
                        horizontal=True
                    )
                
                with col_status2:
                    if st.button("🔄 Update Status", key=f"update_status_{visitor_id}", type="primary"):
                        result, success = update_visitor_status(visitor_id, new_status)
                        if success:
                            st.success(f"✅ Status updated to '{new_status.capitalize()}'")
                            st.toast(f"{visitor['name']} is now {new_status}", icon="🔄")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed: {result.get('detail', 'Unknown error')}")
            
            with tab_delete:
                st.markdown("##### Delete Visitor Record")
                st.warning("⚠️ **Warning:** This action is permanent and cannot be undone!")
                st.info(f"**You are about to delete:**\n- Name: {visitor['name']}\n- Plate: {visitor['license_plate']}\n- Unit: {visitor['unit_number']}")
                
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
                                st.toast(f"Deleted {visitor['name']}", icon="🗑️")
                                st.rerun()
                            else:
                                st.error(f"❌ Failed: {result.get('detail', 'Unknown error')}")
                
                with col_del3:
                    if st.session_state.get('confirm_delete') == visitor_id:
                        st.error("👈 Click 'Confirm Delete' to proceed")
    
    if len(filtered_visitors) == 0 and not search_query:
        st.info("No visitors to display. Register a visitor to get started!")



def main():
    st.set_page_config(
        page_title="Parking Manager",
        page_icon="🚗",
        layout="wide"
    )
    
    st.title("🅿️🚘 Parking Management System")
    st.markdown("🛡️ Register, track, and manage all visitors.🛡️")

    # 1. Check API Connection
    if not check_api_connection():
        st.error("🛑 Cannot connect to FastAPI. Please ensure the backend is running on http://localhost:8000.")
        st.info("Run: python api_task.py")
        return
    
    st.success("✅ WELCOME! CONNECTED TO FASTAPI.")

    # Load visitors first
    visitors, success = get_all_visitors()
    
    if not success:
        st.error("Failed to retrieve visitors from API.")
        return

    # 🔄 UPDATED: Reordered tabs to match your desired order
    tab_register, tab_view, tab_manage, tab_dashboard, tab_chatbot = st.tabs([
        "🚗 Register Visitor", 
        "📋 View All Visitors",
        "⚙️ Edit & Manage",
        "📊 Dashboard",
        "💬 AI Assistant"
    ])
    
    # Make sure the tab functions match the tab order
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
    
    with tab_dashboard:
        display_dashboard(visitors)
    
    # 🆕 NEW: Chatbot tab moved to the end
    with tab_chatbot:
        display_chatbot()

if __name__ == "__main__":
    main()