variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-central-1"
}

variable "instance_type" {
  description = "EC2 instance type. Kafka + Spark + Postgres + the dashboard need real memory: t3.medium (4 GB) is a practical minimum, not the free-tier t2.micro/t3.micro."
  type        = string
  default     = "t3.medium"
}

variable "key_name" {
  description = "Name of an existing EC2 key pair, for SSH access"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to reach SSH and the dashboard port. Restrict this to your own IP (\"x.x.x.x/32\") -- never leave it at 0.0.0.0/0."
  type        = string
}

variable "github_repo_url" {
  description = "Repo the instance clones and runs on boot"
  type        = string
  default     = "https://github.com/mobin-mohammadi1993/crypto-realtime-pipeline.git"
}
