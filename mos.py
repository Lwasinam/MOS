import streamlit as st
import pandas as pd
from pathlib import Path
import csv
import os
import uuid
# <--- MODIFIED: Import the connection class --->
from gsheetsdb import GSheetsDBConnection

# --- Configuration ---
# The app will look for audio files in this folder.
AUDIO_FOLDER = Path("audio_files")

# <--- MODIFIED: No longer need local CSV files for ratings --->
# RATINGS_FILE = Path("mos_ratings.csv") 
MOS_SUMMARY_FILE = Path("mos_summary.csv") # We still create this locally for download

# <--- MODIFIED: Add your Google Sheet details here --->
# This must be the full URL of your Google Sheet
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit"
WORKSHEET_NAME = "Ratings" # The name of the tab you created

# The 5-point MOS scale
RATING_SCALE = {
    "1: Bad": 1,
    "2: Poor": 2,
    "3: Fair": 3,
    "4: Good": 4,
    "5: Excellent": 5
}
CSV_HEADER = ["user_id", "audio_file", "rating"] # Still used for the DataFrame

# <--- MODIFIED: Connect to Google Sheets using st.connection --->
# This uses the secrets from your .streamlit/secrets.toml file
conn = st.connection("gsheets", type=GSheetsDBConnection, sheet_url=GOOGLE_SHEET_URL)


# --- Helper Functions ---

def setup_files():
    """Create the audio folder if it doesn't exist."""
    # Create the audio folder if it's missing
    AUDIO_FOLDER.mkdir(exist_ok=True)
    
    # <--- MODIFIED: No need to create CSV files anymore --->
    # The Google Sheet must be set up manually (see Step 1)

def get_audio_files():
    """Get a sorted list of supported audio files from the folder."""
    supported_extensions = [".wav", ".mp3", ".ogg"]
    files = [
        f.name for f in AUDIO_FOLDER.iterdir() 
        if f.suffix.lower() in supported_extensions and f.is_file()
    ]
    files.sort()  # Ensure a consistent order for all users
    return files

def update_mos_summary():
    """
    Reads all ratings from GOOGLE SHEETS, calculates the
    current MOS, and saves it to a LOCAL summary CSV for download.
    """
    try:
        # <--- MODIFIED: Read from Google Sheets, not a local CSV --->
        df = conn.read(worksheet=WORKSHEET_NAME, usecols=[0, 1, 2])
        
        # Ensure 'rating' column is numeric, handling potential errors
        df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
        df = df.dropna(subset=['rating']) # Drop rows where rating wasn't a number
        
        if df.empty:
            return

        # Calculate MOS per file
        mos_df = df.groupby('audio_file')['rating'].mean().reset_index()
        mos_df = mos_df.rename(columns={'rating': 'MOS'})
        
        # Save the summary LOCALLY for the download button
        mos_df.to_csv(MOS_SUMMARY_FILE, index=False, encoding='utf-8')
        
    except Exception as e:
        st.error(f"Error updating MOS summary: {e}")
        # This can happen if the sheet is empty or headers are wrong
        pass

def save_rating(user_id, audio_file, rating):
    """Append a new rating to the GOOGLE SHEET and update the summary."""
    
    # <--- MODIFIED: Append data to Google Sheets --->
    try:
        # Create a DataFrame for the new row
        new_data = pd.DataFrame(
            [[user_id, audio_file, rating]],
            columns=CSV_HEADER
        )
        
        # 'update' in this context means appending the new rows
        conn.update(
            worksheet=WORKSHEET_NAME,
            data=new_data
        )
        
        # After saving, trigger the summary update
        update_mos_summary()
        
    except Exception as e:
        st.error(f"Failed to save rating to Google Sheets: {e}")
        st.warning("Please check your Google Sheet permissions and setup.")


# --- Streamlit App UI ---

def main():
    st.set_page_config(layout="wide", page_title="MOS Audio Rating")
    st.title("🎧 Audio Quality (MOS) Rating Tool")

    # 1. Setup folders
    setup_files()
    audio_files = get_audio_files()

    if not audio_files:
        st.error(
            f"No audio files found in the '{AUDIO_FOLDER}' folder."
            " Please add some .wav, .mp3, or .ogg files and refresh."
        )
        st.stop()

    # 2. Initialize Streamlit's Session State
    if 'user_id' not in st.session_state:
        st.session_state.user_id = f"user_{str(uuid.uuid4())[:8]}"
    if 'current_audio_index' not in st.session_state:
        st.session_state.current_audio_index = 0
    if 'ratings_submitted' not in st.session_state:
        st.session_state.ratings_submitted = False

    # 3. User Identification & Admin Download
    st.sidebar.header("Your Information")
    st.sidebar.success(f"Rating as: **{st.session_state.user_id}**")
    
    st.sidebar.header("Admin: Download Data")
    
    # <--- MODIFIED: Download button for Raw Ratings --->
    # This now reads from Google Sheets and serves the file
    try:
        all_ratings_df = conn.read(worksheet=WORKSHEET_NAME)
        if not all_ratings_df.empty:
            # Convert DataFrame to CSV string
            csv_data = all_ratings_df.to_csv(index=False).encode('utf-8')
            st.sidebar.download_button(
                label="Download All Ratings (from Google Sheets)",
                data=csv_data,
                file_name="all_mos_ratings.csv",
                mime="text/csv"
            )
        else:
            st.sidebar.info("No raw ratings in Google Sheet yet.")
    except Exception as e:
        st.sidebar.error(f"Could not read from Google Sheet: {e}")

    # <--- MODIFIED: Download button for MOS Summary --->
    # This part remains the same, as update_mos_summary() creates the local file
    if MOS_SUMMARY_FILE.exists():
        with open(MOS_SUMMARY_FILE, "rb") as f:
            st.sidebar.download_button(
                label="Download MOS Summary (mos_summary.csv)",
                data=f,
                file_name=MOS_SUMMARY_FILE.name,
                mime="text/csv"
            )
    else:
        st.sidebar.info("No summary generated yet.")


    # 4. Rating Interface
    
    # Check if all files have been rated
    if st.session_state.current_audio_index >= len(audio_files):
        st.session_state.ratings_submitted = True
        
    if st.session_state.ratings_submitted:
        st.success("🎉 Thank you! You have rated all available audio files.")
        st.balloons()
        
        # Optionally show the *raw* results
        if st.checkbox("Show All Submitted Ratings (from Google Sheets)"):
            try:
                # <--- MODIFIED: Read from Google Sheets --->
                df = conn.read(worksheet=WORKSHEET_NAME)
                st.dataframe(df)
            except Exception as e:
                st.error(f"Could not read ratings: {e}")
        st.stop()

    # Get the current file to rate
    current_file_name = audio_files[st.session_state.current_audio_index]
    current_file_path = AUDIO_FOLDER / current_file_name

    st.header(f"Rating Audio File: `{current_file_name}`")
    st.info(
        f"File {st.session_state.current_audio_index + 1} of {len(audio_files)}"
    )

    # Display audio player
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
            index=2,  # Default to '3: Fair'
            horizontal=True
        )
        
        submit_button = st.form_submit_button(label="Submit Rating and Go to Next")

    # 5. Form Submission Logic
    if submit_button:
        selected_rating = RATING_SCALE[rating_label]
        
        # <--- MODIFIED: This now saves to Google Sheets --->
        save_rating(
            st.session_state.user_id, 
            current_file_name, 
            selected_rating
        )
        
        st.toast(
            f"Rating for '{current_file_name}' saved to Google Sheets!",
            icon="✅"
        )
        
        st.session_state.current_audio_index += 1
        
        if st.session_state.current_audio_index == len(audio_files):
            st.session_state.ratings_submitted = True
        
        st.rerun()

if __name__ == "__main__":
    main()