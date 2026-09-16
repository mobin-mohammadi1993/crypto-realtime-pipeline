output "instance_public_ip" {
  value = aws_instance.pipeline.public_ip
}

output "dashboard_url" {
  value = "http://${aws_instance.pipeline.public_ip}:8501"
}

output "ssh_command" {
  value = "ssh -i <path-to-key>.pem ubuntu@${aws_instance.pipeline.public_ip}"
}
