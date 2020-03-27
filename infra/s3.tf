resource "aws_s3_bucket" "raw" {
  bucket = "raw.data-lagoon.dev"
  acl    = "private"

  tags = {
    Name        = "raw.data-lagoon.dev"
    Environment = "Production"
  }
}
