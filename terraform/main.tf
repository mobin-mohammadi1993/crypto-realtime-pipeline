# Latest Ubuntu 22.04 LTS, official Canonical AMI.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_security_group" "pipeline" {
  name_prefix = "crypto-pipeline-"
  description = "SSH + dashboard access for the crypto streaming pipeline"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  ingress {
    description = "Streamlit dashboard"
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "pipeline" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.pipeline.id]

  root_block_device {
    # The Kafka + Spark + Postgres images alone are several GB; the
    # default 8 GB root volume runs out of room mid-build.
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/cloud-init.sh.tpl", {
    github_repo_url = var.github_repo_url
  })

  tags = {
    Name    = "crypto-realtime-pipeline"
    Project = "crypto-realtime-pipeline"
  }
}
