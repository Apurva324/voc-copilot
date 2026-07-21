import pandas as pd
from google_play_scraper import Sort, reviews

# 1. Zomato's unique Google Play Store Package ID
ZOMATO_APP_ID = "com.application.zomato"


def fetch_latest_zomato_reviews(count=100):
    print(f"Fetching the latest {count} reviews for Zomato...")

    # 2. Call the scraper API
    result, continuation_token = reviews(
        ZOMATO_APP_ID,
        lang="en",  # Language
        country="in",  # Country code (India)
        sort=Sort.NEWEST,  # Always get the latest updates
        count=count,  # Number of reviews to fetch
    )

    if not result:
        print("No reviews found or extraction failed.")
        return None

    # 3. Convert raw dictionary list to a Pandas DataFrame
    df = pd.DataFrame(result)

    # 4. Select and rename only the columns relevant to your VoC Copilot
    df_cleaned = df[
        [
            "reviewId",
            "userName",
            "score",
            "content",
            "at",
            "reviewCreatedVersion",
        ]
    ].copy()
    df_cleaned.columns = [
        "source_id",
        "user",
        "rating",
        "feedback_text",
        "timestamp",
        "app_version",
    ]

    # Add a channel column so your system knows where this came from
    df_cleaned["channel"] = "Google Play Store"

    return df_cleaned


if __name__ == "__main__":
    # Fetch data
    reviews_df = fetch_latest_zomato_reviews(count=100)

    if reviews_df is not None:
        # 5. Let's isolate the critical signals (1 and 2-star reviews)
        negative_feedback = reviews_df[reviews_df["rating"] <= 2]

        print("\n--- SCRAPE SUCCESSFUL ---")
        print(f"Total reviews pulled: {len(reviews_df)}")
        print(f"Critical/Negative signals found: {len(negative_feedback)}")

        # 6. Preview the top 3 worst complaints for your dashboard
        print("\n Preview of critical complaints:")
        for idx, row in negative_feedback.head(3).iterrows():
            print(f"\n[{row['user']} - {row['rating']}]")
            print(f"Text: {row['feedback_text']}")
            print(f"Version: {row['app_version']} | Time: {row['timestamp']}")