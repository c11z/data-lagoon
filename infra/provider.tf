variable "aws_access_key" {
  type = string
}

variable "aws_secret_key" {
  type = string
}

locals {
}

provider "aws" {
  version    = "~> 2.0"
  region     = "us-west-2"
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
}
