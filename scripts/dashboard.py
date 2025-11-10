#!/usr/bin/env python3
"""
Streamlit dashboard to visualize survey sentiment analysis results from DynamoDB.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import boto3
import json
from datetime import datetime, timedelta
from decimal import Decimal
import os

# Page configuration
st.set_page_config(
    page_title="Survey Sentiment Dashboard",
    page_icon="📊",
    layout="wide"
)

# Initialize DynamoDB client
@st.cache_resource
def get_dynamodb_client():
    """Get DynamoDB client with caching."""
    region = os.environ.get('AWS_REGION', 'ap-southeast-2')
    return boto3.resource('dynamodb', region_name=region)

# Get table name from environment or user input
def get_table_name():
    """Get DynamoDB table name."""
    table_name = os.environ.get('DYNAMODB_TABLE_NAME')
    if not table_name:
        table_name = st.sidebar.text_input(
            "DynamoDB Table Name",
            value="survey-sentiment-demo-results",
            help="Enter the DynamoDB table name from Terraform output"
        )
    return table_name

# Query DynamoDB
@st.cache_data(ttl=30)  # Cache for 30 seconds
def fetch_survey_results(table_name: str):
    """Fetch all survey results from DynamoDB."""
    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(table_name)

        # Scan table (for demo purposes - in production, use query with GSI)
        response = table.scan()
        items = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        return items
    except Exception as e:
        error_msg = str(e)
        if "ResourceNotFoundException" in error_msg:
            st.error(f"Table '{table_name}' not found. Verify the table name and AWS region.")
            st.info(f"Current region: {os.environ.get('AWS_REGION', 'ap-southeast-2')}")
        else:
            st.error(f"Error fetching data: {error_msg}")
        return []


def convert_decimal(obj):
    """Convert Decimal to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def process_data(items):
    """Process DynamoDB items into a pandas DataFrame."""
    if not items:
        return pd.DataFrame()

    processed = []
    for item in items:
        # Parse sentiment scores if stored as JSON string
        score_str = item.get('score', '{}')
        if isinstance(score_str, str):
            try:
                scores = json.loads(score_str)
            except:
                scores = {}
        else:
            scores = score_str

        processed.append({
            'surveyId': item.get('surveyId', ''),
            'customerId': item.get('customerId', ''),
            'rating': float(item.get('rating', 0)),
            'text': item.get('text', ''),
            'sentiment': item.get('sentiment', 'UNKNOWN'),
            'positive_score': scores.get('Positive', 0.0),
            'negative_score': scores.get('Negative', 0.0),
            'neutral_score': scores.get('Neutral', 0.0),
            'mixed_score': scores.get('Mixed', 0.0),
            'createdAt': datetime.fromtimestamp(int(item.get('createdAt', 0))),
            'expiresAt': datetime.fromtimestamp(int(item.get('expiresAt', 0))),
        })

    df = pd.DataFrame(processed)

    if not df.empty:
        df['createdAt'] = pd.to_datetime(df['createdAt'])
        df['expiresAt'] = pd.to_datetime(df['expiresAt'])

    return df


def main():
    """Main dashboard function."""
    st.title("📊 Survey Sentiment Analysis Dashboard")
    st.markdown("Real-time visualization of survey sentiment analysis results")

    # Sidebar configuration
    table_name = get_table_name()

    if not table_name:
        st.warning("Please enter the DynamoDB table name in the sidebar.")
        return

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data", type="primary"):
        st.cache_data.clear()

    # Fetch data
    with st.spinner("Loading survey results..."):
        items = fetch_survey_results(table_name)
        df = process_data(items)

    if df.empty:
        st.warning("No survey results found in DynamoDB. Run the send_surveys.py script first.")
        return

    # Key Metrics
    st.header("📈 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Surveys", len(df))

    with col2:
        avg_rating = df['rating'].mean()
        st.metric("Average Rating", f"{avg_rating:.2f}")

    with col3:
        positive_pct = (df['sentiment'] == 'POSITIVE').sum() / len(df) * 100
        st.metric("Positive Sentiment", f"{positive_pct:.1f}%")

    with col4:
        negative_pct = (df['sentiment'] == 'NEGATIVE').sum() / len(df) * 100
        st.metric("Negative Sentiment", f"{negative_pct:.1f}%")

    st.divider()

    # Charts Row 1
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sentiment Distribution")
        sentiment_counts = df['sentiment'].value_counts()
        fig_pie = px.pie(
            values=sentiment_counts.values,
            names=sentiment_counts.index,
            color_discrete_map={
                'POSITIVE': '#2ecc71',
                'NEGATIVE': '#e74c3c',
                'NEUTRAL': '#f39c12',
                'MIXED': '#95a5a6'
            }
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, width='stretch')

    with col2:
        st.subheader("Rating Distribution")
        rating_counts = df['rating'].value_counts().sort_index()
        fig_bar = px.bar(
            x=rating_counts.index,
            y=rating_counts.values,
            labels={'x': 'Rating', 'y': 'Count'},
            color=rating_counts.values,
            color_continuous_scale='Viridis'
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, width='stretch')

    # Charts Row 2
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sentiment Over Time")
        df_time = df.groupby([df['createdAt'].dt.date, 'sentiment']).size().reset_index(name='count')
        df_time['createdAt'] = pd.to_datetime(df_time['createdAt'])

        fig_line = px.line(
            df_time,
            x='createdAt',
            y='count',
            color='sentiment',
            labels={'createdAt': 'Date', 'count': 'Count'},
            color_discrete_map={
                'POSITIVE': '#2ecc71',
                'NEGATIVE': '#e74c3c',
                'NEUTRAL': '#f39c12',
                'MIXED': '#95a5a6'
            }
        )
        st.plotly_chart(fig_line, width='stretch')

    with col2:
        st.subheader("Sentiment Score Breakdown")
        score_cols = ['positive_score', 'negative_score', 'neutral_score', 'mixed_score']
        avg_scores = df[score_cols].mean()

        fig_scores = go.Figure(data=[
            go.Bar(
                x=['Positive', 'Negative', 'Neutral', 'Mixed'],
                y=[avg_scores['positive_score'], avg_scores['negative_score'],
                   avg_scores['neutral_score'], avg_scores['mixed_score']],
                marker_color=['#2ecc71', '#e74c3c', '#f39c12', '#95a5a6']
            )
        ])
        fig_scores.update_layout(
            yaxis_title="Average Confidence Score",
            showlegend=False
        )
        st.plotly_chart(fig_scores, width='stretch')

    st.divider()

    # Filters and Data Table
    st.subheader("📋 Survey Data")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        sentiment_filter = st.multiselect(
            "Filter by Sentiment",
            options=df['sentiment'].unique(),
            default=df['sentiment'].unique()
        )

    with col2:
        rating_filter = st.multiselect(
            "Filter by Rating",
            options=sorted(df['rating'].unique()),
            default=sorted(df['rating'].unique())
        )

    with col3:
        date_range = st.date_input(
            "Date Range",
            value=(df['createdAt'].min().date(), df['createdAt'].max().date()),
            min_value=df['createdAt'].min().date(),
            max_value=df['createdAt'].max().date()
        )

    # Apply filters
    filtered_df = df[
        (df['sentiment'].isin(sentiment_filter)) &
        (df['rating'].isin(rating_filter)) &
        (df['createdAt'].dt.date >= date_range[0]) &
        (df['createdAt'].dt.date <= date_range[1])
    ]

    # Display filtered data
    st.dataframe(
        filtered_df[['surveyId', 'customerId', 'rating', 'sentiment', 'text', 'createdAt']],
        width='stretch',
        hide_index=True
    )

    st.caption(f"Showing {len(filtered_df)} of {len(df)} surveys")


if __name__ == "__main__":
    main()
