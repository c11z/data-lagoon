from urllib.request import urlopen
from prefect import task, Flow, Parameter  # type: ignore
from prefect.tasks.secrets import EnvVarSecret  # type: ignore
from prefect.tasks.aws.s3 import S3Upload  # type: ignore
from prefect.client import secrets  # type: ignore

BASE_URL = "https://raw.githubusercontent.com/COVID19Tracking/covid-tracking-data"


@task
def download_csv(base_url: str, branch: str, path: str) -> str:
    url = f"{BASE_URL}/{branch}/{path}"
    response = urlopen(url)
    data = response.read().decode("utf-8")
    print(url)
    return data


def main():
    s3upload = S3Upload(
        bucket="raw.data-lagoon.dev"
    )
    with Flow("etl") as flow:

        branch = Parameter("branch", default="master")
        states_current_path = Parameter(
            "states_current_path", default="data/states_current.csv"
        )

        data = download_csv(BASE_URL, branch, states_current_path)
        s3upload(data, aws_credentials_secret="AWS_CREDENTIALS", key=states_current_path)

    flow.run()


if __name__ == "__main__":
    main()
