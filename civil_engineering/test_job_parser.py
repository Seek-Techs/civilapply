from civil_engineering.job_parser import parse_job_description


def main():
    with open("sample_job.txt", "r", encoding="utf-8") as f:
        text = f.read()

    job = parse_job_description(text)
    print("Parsed Job:")
    print(job)


if __name__ == "__main__":
    main()
