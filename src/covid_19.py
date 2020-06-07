from urllib.request import urlopen

import pendulum
from prefect import Flow, Parameter, context, task
from prefect.tasks.aws.s3 import S3Upload

BASE_URL = "https://raw.githubusercontent.com/COVID19Tracking/covid-tracking-data"


@task
def download_github_csv(base_url: str, branch: str, path: str) -> str:
    log = context["logger"]
    url = f"{BASE_URL}/{branch}/{path}"
    log.info(url)
    response = urlopen(url)
    data = response.read().decode("utf-8")
    log.info(data)
    return data


def main():
    s3upload = S3Upload(bucket="raw.data-lagoon.dev")
    with Flow("etl") as flow:

        branch = Parameter("branch", default="master")
        states_current_path = Parameter(
            "states_current_path", default="data/states_current.csv"
        )

        data = download_github_csv(BASE_URL, branch, states_current_path)
        s3upload(
            data,
            aws_credentials_secret="AWS_CREDENTIALS",
            key=f"covid_19/states_current/ds={pendulum.now('UTC').to_date_string()}/data.csv",
        )
        
    flow.run()


if __name__ == "__main__":
    main()
