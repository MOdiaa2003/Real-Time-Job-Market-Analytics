import time
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from kafka import KafkaConsumer
import simplejson as json
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import numpy as np

# Page configuration
st.set_page_config(
    page_title="Real-Time Job Matching Dashboard",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Function to fetch data from Kafka - NO CACHING
def fetch_kafka_data(topic_name, max_messages=5000):
    """Fetch data from Kafka topic - creates fresh consumer each time"""
    try:
        consumer = KafkaConsumer(
            topic_name,
            bootstrap_servers='localhost:9092',
            auto_offset_reset='earliest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            enable_auto_commit=False,
            consumer_timeout_ms=3000,
            group_id=None  # No consumer group = always read from beginning
        )
        
        data = []
        # Poll multiple times to ensure we get all messages
        for _ in range(10):
            messages = consumer.poll(timeout_ms=500, max_records=500)
            if not messages:
                break
            for message_batch in messages.values():
                for message in message_batch:
                    data.append(message.value)
        
        consumer.close()
        return data
    except Exception as e:
        st.sidebar.error(f"Error fetching {topic_name}: {str(e)}")
        return []

@st.cache_data(show_spinner=False)
def split_frame(input_df, rows):
    """Split dataframe into chunks for pagination"""
    input_df = input_df.reset_index(drop=True)
    df = [input_df.iloc[i: i + rows] for i in range(0, len(input_df), rows)]
    return df

def paginate_table(table_data):
    """Display paginated table with sorting options"""
    top_menu = st.columns(3)
    with top_menu[0]:
        sort = st.radio("Sort Data", options=["Yes", "No"], horizontal=True, index=1)
    
    if sort == "Yes":
        with top_menu[1]:
            sort_field = st.selectbox("Sort By", options=table_data.columns)
        with top_menu[2]:
            sort_direction = st.radio("Direction", options=["⬆️", "⬇️"], horizontal=True)
        table_data = table_data.sort_values(
            by=sort_field, ascending=sort_direction == "⬆️", ignore_index=True
        )
    
    pagination = st.container()
    bottom_menu = st.columns((4, 1, 1))
    
    with bottom_menu[2]:
        batch_size = st.selectbox("Page Size", options=[10, 25, 50, 100])
    with bottom_menu[1]:
        total_pages = max(1, int(len(table_data) / batch_size))
        current_page = st.number_input("Page", min_value=1, max_value=total_pages, step=1)
    with bottom_menu[0]:
        st.markdown(f"Page **{current_page}** of **{total_pages}**")
    
    pages = split_frame(table_data, batch_size)
    pagination.dataframe(data=pages[current_page - 1], use_container_width=True)

# Main update function
def update_data():
    """Fetch and display all dashboard data"""
    
    # Last refresh indicator
    last_refresh = st.empty()
    last_refresh.text(f"Last refreshed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ========== FETCH DATA FROM KAFKA TOPICS ==========

# Job Applications
    applications_data = fetch_kafka_data("job_applications")
    applications_df = pd.DataFrame(applications_data)

    # Job Posts
    job_posts_data = fetch_kafka_data("job_posts")
    job_posts_df = pd.DataFrame(job_posts_data)

    # Candidates
    candidates_data = fetch_kafka_data("candidate_info")
    candidates_df = pd.DataFrame(candidates_data)

    # Debug - KEEP THIS to verify counts
    st.sidebar.write(f"📊 Data: Apps={len(applications_df)}, Jobs={len(job_posts_df)}, Candidates={len(candidates_df)}")
        # ========== KEY METRICS ==========
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_applications = len(applications_df) if not applications_df.empty else 0
        st.metric("Total Applications", f"{total_applications:,}")
    
    with col2:
        total_jobs = len(job_posts_df) if not job_posts_df.empty else 0
        st.metric("Active Job Posts", f"{total_jobs:,}")
    
    with col3:
        total_candidates = len(candidates_df) if not candidates_df.empty else 0
        st.metric("Active Candidates", f"{total_candidates:,}")
    
    with col4:
        if not applications_df.empty and 'compatibility_score' in applications_df.columns:
            avg_match_score = applications_df['compatibility_score'].mean()
            st.metric("Avg Match Score", f"{avg_match_score:.1f}%")
        else:
            st.metric("Avg Match Score", "N/A")
    
    with col5:
        if not applications_df.empty and 'status' in applications_df.columns:
            shortlisted = len(applications_df[applications_df['status'] == 'Shortlisted'])
            st.metric("Shortlisted", f"{shortlisted:,}")
        else:
            st.metric("Shortlisted", "0")
    
        # ========== CHART 1: Applications Over Time (8 Fixed Intervals - Line Chart) ==========
        st.markdown("---")
    st.header("📈 1. Application Trends Over Time")

    if not applications_df.empty and 'application_date' in applications_df.columns:
        apps_time_df = applications_df.copy()
        apps_time_df['application_date'] = pd.to_datetime(apps_time_df['application_date'])
        
        # Define 8 fixed time intervals (3 hours each)
        def get_time_interval(hour):
            intervals = [
                (0, 3, "12:00 AM - 3:00 AM"),
                (3, 6, "3:00 AM - 6:00 AM"), 
                (6, 9, "6:00 AM - 9:00 AM"),
                (9, 12, "9:00 AM - 12:00 PM"),
                (12, 15, "12:00 PM - 3:00 PM"),
                (15, 18, "3:00 PM - 6:00 PM"),
                (18, 21, "6:00 PM - 9:00 PM"),
                (21, 24, "9:00 PM - 12:00 AM")
            ]
            
            for start, end, label in intervals:
                if start <= hour < end:
                    return label
            return "Unknown"
        
        # Apply time interval grouping
        apps_time_df['hour'] = apps_time_df['application_date'].dt.hour
        apps_time_df['time_interval'] = apps_time_df['hour'].apply(get_time_interval)
        
        # Define the order of intervals for proper sorting
        interval_order = [
            "12:00 AM - 3:00 AM", "3:00 AM - 6:00 AM", "6:00 AM - 9:00 AM",
            "9:00 AM - 12:00 PM", "12:00 PM - 3:00 PM", "3:00 PM - 6:00 PM", 
            "6:00 PM - 9:00 PM", "9:00 PM - 12:00 AM"
        ]
        
        # Group by time intervals
        interval_apps = apps_time_df.groupby('time_interval').size().reset_index(name='applications')
        
        # Convert to categorical to maintain order
        interval_apps['time_interval'] = pd.Categorical(
            interval_apps['time_interval'], 
            categories=interval_order, 
            ordered=True
        )
        interval_apps = interval_apps.sort_values('time_interval')
        
        fig1 = px.line(
            interval_apps,
            x='time_interval',
            y='applications',
            title="Applications Submitted Per Time Interval",
            labels={'time_interval': 'Time Interval', 'applications': 'Number of Applications'},
            color_discrete_sequence=['#1f77b4']
        )
        
        # Add markers and improve the line
        fig1.update_traces(
            mode='lines+markers', 
            marker=dict(size=8, color='#1f77b4'),
            line=dict(width=3)
        )
        
        fig1.update_layout(
            xaxis_title="Time Interval",
            yaxis_title="Number of Applications",
            xaxis={'type': 'category', 'tickangle': 45}
        )
        
        st.plotly_chart(fig1, use_container_width=True)
        
    else:
        st.info("No application data available yet.")
    
    # ========== CHART 2: Top Job Categories & Match Distribution ==========
    st.markdown("---")
    st.header("🎯 2. Top Job Categories by Applications")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not applications_df.empty and 'job_post_family_group' in applications_df.columns:
            category_counts = applications_df['job_post_family_group'].value_counts().head(10)
            
            fig2a = px.bar(
                x=category_counts.values,
                y=category_counts.index,
                orientation='h',
                title="Top 10 Job Families by Application Volume",
                labels={'x': 'Number of Applications', 'y': 'Job Family'},
                color=category_counts.values,
                color_continuous_scale='Viridis'
            )
            fig2a.update_layout(showlegend=False, height=500)
            st.plotly_chart(fig2a, use_container_width=True)
        else:
            st.info("Job category data not available.")
    
    with col2:
        if not applications_df.empty and 'compatibility_score' in applications_df.columns:
            # Score distribution
            fig2b = px.histogram(
                applications_df,
                x='compatibility_score',
                nbins=20,
                title="Compatibility Score Distribution",
                labels={'compatibility_score': 'Match Score (%)', 'count': 'Frequency'},
                color_discrete_sequence=['#ff7f0e']
            )
            fig2b.update_layout(height=500)
            st.plotly_chart(fig2b, use_container_width=True)
        else:
            st.info("Compatibility score data not available.")
    
    # ========== CHART 3: Application Status Breakdown ==========
    st.markdown("---")
    st.header("📊 3. Application Status Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not applications_df.empty and 'status' in applications_df.columns:
            status_counts = applications_df['status'].value_counts()
            
            fig3a = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="Application Status Distribution",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig3a.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig3a, use_container_width=True)
        else:
            st.info("Status data not available.")
    
    with col2:
        if not applications_df.empty and 'compatibility_score' in applications_df.columns and 'status' in applications_df.columns:
            # Box plot: Score distribution by status
            fig3b = px.box(
                applications_df,
                x='status',
                y='compatibility_score',
                title="Match Score by Application Status",
                labels={'status': 'Status', 'compatibility_score': 'Match Score (%)'},
                color='status',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig3b.update_layout(showlegend=False)
            st.plotly_chart(fig3b, use_container_width=True)
        else:
            st.info("Score/status data not available.")
    
    # ========== CHART 4: Job Market Insights ==========
    st.markdown("---")
    st.header("💼 4. Job Market Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not job_posts_df.empty and 'work_mode' in job_posts_df.columns:
            work_mode_counts = job_posts_df['work_mode'].value_counts()
            
            fig4a = px.bar(
                x=work_mode_counts.index,
                y=work_mode_counts.values,
                title="Job Postings by Work Mode",
                labels={'x': 'Work Mode', 'y': 'Number of Jobs'},
                color=work_mode_counts.values,
                color_continuous_scale='Blues'
            )
            fig4a.update_layout(showlegend=False)
            st.plotly_chart(fig4a, use_container_width=True)
        else:
            st.info("Work mode data not available.")
    
    with col2:
        if not job_posts_df.empty and 'employment_type' in job_posts_df.columns:
            emp_type_counts = job_posts_df['employment_type'].value_counts()
            
            fig4b = px.pie(
                values=emp_type_counts.values,
                names=emp_type_counts.index,
                title="Employment Type Distribution",
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            st.plotly_chart(fig4b, use_container_width=True)
        else:
            st.info("Employment type data not available.")
    
    # ========== CHART 5: Candidate & Salary Insights ==========
    st.markdown("---")
    st.header("👥 5. Candidate & Compensation Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not candidates_df.empty and 'education_level' in candidates_df.columns:
            edu_counts = candidates_df['education_level'].value_counts()
            
            fig5a = px.bar(
                x=edu_counts.values,
                y=edu_counts.index,
                orientation='h',
                title="Candidates by Education Level",
                labels={'x': 'Number of Candidates', 'y': 'Education Level'},
                color=edu_counts.values,
                color_continuous_scale='Greens'
            )
            fig5a.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig5a, use_container_width=True)
        else:
            st.info("Education data not available.")
    
    with col2:
        if not job_posts_df.empty and 'salary' in job_posts_df.columns:
            salary_df = job_posts_df[job_posts_df['salary'] > 0].copy()
            
            if not salary_df.empty:
                fig5b = px.histogram(
                    salary_df,
                    x='salary',
                    nbins=30,
                    title="Job Salary Distribution",
                    labels={'salary': 'Salary ($)', 'count': 'Number of Jobs'},
                    color_discrete_sequence=['#d62728']
                )
                fig5b.update_layout(height=400)
                st.plotly_chart(fig5b, use_container_width=True)
            else:
                st.info("Salary data not available.")
        else:
            st.info("Salary data not available.")
    
    # ========== BONUS CHART: Geographic Distribution ==========
    st.markdown("---")
    st.header("🌍 6. Geographic Distribution of Jobs")
    
    if not job_posts_df.empty and 'country' in job_posts_df.columns:
        country_counts = job_posts_df['country'].value_counts().head(15)
        
        fig6 = px.treemap(
            names=country_counts.index,
            parents=[""] * len(country_counts),
            values=country_counts.values,
            title="Job Postings by Country (Top 15)",
            color=country_counts.values,
            color_continuous_scale='RdYlGn'
        )
        st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("Country data not available.")
    
    # ========== DETAILED TABLES ==========
    st.markdown("---")
    st.header("📋 Recent Applications (Detailed View)")
    
    if not applications_df.empty:
        display_cols = ['application_id', 'candidate_id', 'post_id', 'compatibility_score', 
                       'status', 'application_method', 'timestamp']
        available_cols = [col for col in display_cols if col in applications_df.columns]
        
        recent_apps = applications_df[available_cols].sort_values('timestamp', ascending=False).head(100)
        paginate_table(recent_apps)
    else:
        st.info("No applications to display.")
    
    # Update session state
    st.session_state['last_update'] = time.time()

# Sidebar
def sidebar():
    """Configure sidebar with refresh controls"""
    if st.session_state.get('last_update') is None:
        st.session_state['last_update'] = time.time()
    
    st.sidebar.title("⚙️ Dashboard Controls")
    
    # Refresh interval slider
    refresh_interval = st.sidebar.slider("Auto-refresh interval (seconds)", 5, 60, 10)
    st_autorefresh(interval=refresh_interval * 1000, key="auto")
    
    # Manual refresh button
    if st.sidebar.button('🔄 Refresh Data Now', use_container_width=True):
        update_data()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Data Sources")
    st.sidebar.info("""
    - **job_applications**: Real-time applications
    - **job_posts**: Active job listings
    - **candidate_info**: Candidate profiles
    """)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💡 Tips")
    st.sidebar.markdown("""
    - Adjust refresh rate for real-time updates
    - Use sorting and pagination in tables
    - Hover over charts for details
    """)

# Main app
st.title('💼 Real-Time Job Matching Dashboard')
st.markdown("### Monitor job applications, market trends, and candidate insights in real-time")

# Display sidebar and main content
sidebar()
update_data()