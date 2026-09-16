# Deploying to AWS

This provisions one EC2 instance, installs Docker on it, clones this
repo, and runs `docker compose up -d --build` -- the same stack the main
[README](../README.md) runs locally, just on a real server instead of a
laptop.

It hasn't been applied against a live AWS account. The HCL is correct and
`terraform validate`/`fmt` pass in CI on every push, but nobody's run
`terraform apply` against real infrastructure yet.

## Before running this

1. An AWS account with billing set up, and credentials available locally
   (`aws configure`, or the usual `AWS_ACCESS_KEY_ID` /
   `AWS_SECRET_ACCESS_KEY` environment variables).
2. An EC2 key pair already created in the target region, for SSH access.
3. Your own public IP, to restrict `allowed_ssh_cidr` to just you --
   don't leave it open to the whole internet.

## Usage

```bash
cd terraform
terraform init
terraform plan -var="key_name=your-key-pair" -var="allowed_ssh_cidr=YOUR_IP/32"
terraform apply -var="key_name=your-key-pair" -var="allowed_ssh_cidr=YOUR_IP/32"
```

First boot takes a few minutes: installing Docker, then pulling and
building five images. Once `terraform apply` finishes, the dashboard
isn't up yet -- give it 5-10 more minutes, then check the `dashboard_url`
output.

```bash
terraform destroy -var="key_name=your-key-pair" -var="allowed_ssh_cidr=YOUR_IP/32"
```

## Cost

`t3.medium` runs about $0.04-0.05/hour depending on region -- roughly
$1/day if left running, nothing at all once destroyed. This isn't
free-tier eligible; Kafka + Spark + Postgres + the dashboard genuinely
need the memory a free-tier `t2.micro` doesn't have. Run `terraform
destroy` when you're done looking at it.
