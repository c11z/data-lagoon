resource "aws_iam_user" "svc_data_lagoon" {
    name      = "svc_data_lagoon"
    path      = "/"
    tags      = {}
}

resource "aws_iam_role" "snowflake" {
    assume_role_policy    = jsonencode(
        {
            Statement = [
                {
                    Action    = "sts:AssumeRole"
                    Condition = {}
                    Effect    = "Allow"
                    Principal = {
                        AWS = "arn:aws:iam::498990102557:root"
                    }
                },
            ]
            Version   = "2012-10-17"
        }
    )
    force_detach_policies = false
    name                  = "SnowflakeRole"
    path                  = "/"
    tags                  = {}
}


resource "aws_iam_user" "snowflake" {
  name = "svc_snowflake"

  tags = {}
}

resource "aws_iam_access_key" "snowflake" {
  user = aws_iam_user.snowflake.name
}

output "svc_snowflake_key_id" {
  value = aws_iam_access_key.snowflake.id
}

output "svc_snowflake_secret_key" {
  value = aws_iam_access_key.snowflake.secret
}

resource "aws_iam_user_policy_attachment" "snowflake_s3_readonly" {
  user       = aws_iam_user.snowflake.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
}
