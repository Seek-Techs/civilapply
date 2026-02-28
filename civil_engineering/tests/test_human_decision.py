from civil_engineering.review.decision_updater import update_human_decision

if __name__ == "__main__":
    result = update_human_decision("job_004", "approve")
    print("UPDATED REVIEW PACKET:")
    print(result)
