import streamlit as st
import pandas as pd
from pathlib import Path
import os
import uuid
from streamlit_gsheets import GSheetsConnection

# --- Configuration ---
# The app will look for audio files in this folder.
AUDIO_FOLDER = Path("audio_files")
MOS_SUMMARY_FILE = Path("mos_summary.csv")

# Add your Google Sheet URL here
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1VV_78onqKDKgU3kh8ND8FAd7OU2c5qf89ydJFajAtvk/edit?gid=0#gid=0"
WORKSHEET_NAME = "Ratings"

# The 5-point MOS scale
RATING_SCALE = {
    "1: Bad": 1,
    "2: Poor": 2,
    "3: Fair": 3,
    "4: Good": 4,
    "5: Excellent": 5
}

# --- Helper Functions ---

def get_gsheets_connection():
    """Get or create the Google Sheets connection."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        st.info("Make sure your secrets.toml is properly configured.")
        return None

def setup_files():
    """Create the audio folder if it doesn't exist."""
    AUDIO_FOLDER.mkdir(exist_ok=True)

def get_audio_files():
    """Get a sorted list of supported audio files from the folder."""
    supported_extensions = [".wav", ".mp3", ".ogg"]
    files = [
        f.name for f in AUDIO_FOLDER.iterdir() 
        if f.suffix.lower() in supported_extensions and f.is_file()
    ]
    files.sort()
    return files

def update_mos_summary(conn):
    """
    Reads all ratings from Google Sheets, calculates MOS,
    and saves summary locally for download.
    """
    try:
        df = conn.read(worksheet=WORKSHEET_NAME, ttl=0)
        
        if df.empty:
            return
        
        # Ensure proper column names
        if 'rating' in df.columns:
            df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
            df = df.dropna(subset=['rating'])
            
            if not df.empty and 'audio_file' in df.columns:
                mos_df = df.groupby('audio_file')['rating'].mean().reset_index()
                mos_df = mos_df.rename(columns={'rating': 'MOS'})
                mos_df.to_csv(MOS_SUMMARY_FILE, index=False, encoding='utf-8')
        
    except Exception as e:
        st.warning(f"Note: Could not update MOS summary: {e}")
        pass

def save_rating(conn, user_id, audio_file, rating):
    """Append a new rating to Google Sheets."""
    try:
        # Read existing data
        existing_df = conn.read(worksheet=WORKSHEET_NAME, ttl=0)
        
        # Create new row
        new_row = pd.DataFrame({
            'user_id': [user_id],
            'audio_file': [audio_file],
            'rating': [rating]
        })
        
        # Append to existing data
        if existing_df.empty:
            updated_df = new_row
        else:
            updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        
        # Write back to sheet
        conn.update(worksheet=WORKSHEET_NAME, data=updated_df)
        
        # Update summary
        update_mos_summary(conn)
        
        return True
        
    except Exception as e:
        st.error(f"Failed to save rating: {e}")
        return False


# --- Streamlit App UI ---

def main():
    st.set_page_config(layout="wide", page_title="MOS Audio Rating")
    st.title("🎧 Audio Quality (MOS) Rating Tool")

    # Setup
    setup_files()
    audio_files = get_audio_files()

    if not audio_files:
        st.error(
            f"No audio files found in the '{AUDIO_FOLDER}' folder. "
            "Please add some .wav, .mp3, or .ogg files and refresh."
        )
        st.stop()

    # Get Google Sheets connection
    conn = get_gsheets_connection()
    if conn is None:
        st.stop()

    # Initialize Session State
    if 'user_id' not in st.session_state:
        st.session_state.user_id = f"user_{str(uuid.uuid4())[:8]}"
    if 'current_audio_index' not in st.session_state:
        st.session_state.current_audio_index = 0
    if 'ratings_submitted' not in st.session_state:
        st.session_state.ratings_submitted = False

    # Sidebar
    st.sidebar.header("Your Information")
    st.sidebar.success(f"Rating as: **{st.session_state.user_id}**")
    
    st.sidebar.header("Admin: Download Data")
    
    # Download raw ratings
    try:
        all_ratings_df = conn.read(worksheet=WORKSHEET_NAME, ttl=0)
        if not all_ratings_df.empty:
            csv_data = all_ratings_df.to_csv(index=False).encode('utf-8')
            st.sidebar.download_button(
                label="Download All Ratings",
                data=csv_data,
                file_name="all_mos_ratings.csv",
                mime="text/csv"
            )
        else:
            st.sidebar.info("No ratings yet.")
    except Exception as e:
        st.sidebar.error(f"Could not read ratings: {e}")

    # Download MOS summary
    if MOS_SUMMARY_FILE.exists():
        with open(MOS_SUMMARY_FILE, "rb") as f:
            st.sidebar.download_button(
                label="Download MOS Summary",
                data=f,
                file_name=MOS_SUMMARY_FILE.name,
                mime="text/csv"
            )

    # Check completion
    if st.session_state.current_audio_index >= len(audio_files):
        st.session_state.ratings_submitted = True
        
    if st.session_state.ratings_submitted:
        st.success("🎉 Thank you! You have rated all available audio files.")
        st.balloons()
        
        if st.checkbox("Show All Submitted Ratings"):
            try:
                df = conn.read(worksheet=WORKSHEET_NAME, ttl=0)
                st.dataframe(df)
            except Exception as e:
                st.error(f"Could not read ratings: {e}")
        st.stop()

    # Current file
    current_file_name = audio_files[st.session_state.current_audio_index]
    current_file_path = AUDIO_FOLDER / current_file_name

    st.header(f"Rating Audio File: `{current_file_name}`")
    st.info(f"File {st.session_state.current_audio_index + 1} of {len(audio_files)}")

    # Audio player
    try:
        audio_bytes = current_file_path.read_bytes()
        st.audio(audio_bytes)
    except Exception as e:
        st.error(f"Error loading audio file: {e}")
        st.stop()

    # Rating form
    with st.form(key="mos_form"):
        st.subheader("Please rate the quality of the audio:")
        
        rating_label = st.radio(
            label="Rating (1=Bad, 5=Excellent)",
            options=RATING_SCALE.keys(),
            index=2,
            horizontal=True
        )
        
        submit_button = st.form_submit_button(label="Submit Rating and Go to Next")

    # Form submission
    if submit_button:
        selected_rating = RATING_SCALE[rating_label]
        
        
        success = save_rating(
            conn,
            st.session_state.user_id, 
            current_file_name, 
            selected_rating
        )
        
        if success:
            st.toast(f"Rating for audio'{current_file_name}' saved!", icon="✅")
            st.session_state.current_audio_index += 1
            
            if st.session_state.current_audio_index == len(audio_files):
                st.session_state.ratings_submitted = True
            
            st.rerun()

if __name__ == "__main__":
    main()