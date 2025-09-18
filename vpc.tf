provider "aws" {
  region = "ap-northeast-2"
}

#==================================================
# VPC
#==================================================
resource "aws_vpc" "community_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "community-vpc"
  }
}

#==================================================
# Subnets
#==================================================
resource "aws_subnet" "public_subnet_a" {
  vpc_id                  = aws_vpc.community_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "ap-northeast-2a"
  map_public_ip_on_launch = true

  tags = {
    Name = "public-subnet-a"
  }
}

resource "aws_subnet" "public_subnet_c" {
  vpc_id                  = aws_vpc.community_vpc.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "ap-northeast-2c"
  map_public_ip_on_launch = true

  tags = {
    Name = "public-subnet-c"
  }
}

resource "aws_subnet" "private_subnet_a" {
  vpc_id            = aws_vpc.community_vpc.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "ap-northeast-2a"

  tags = {
    Name = "private-subnet-a"
  }
}

resource "aws_subnet" "private_subnet_c" {
  vpc_id            = aws_vpc.community_vpc.id
  cidr_block        = "10.0.4.0/24"
  availability_zone = "ap-northeast-2c"

  tags = {
    Name = "private-subnet-c"
  }
}

#==================================================
# Internet Gateway
#==================================================
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.community_vpc.id

  tags = {
    Name = "community-igw"
  }
}

#==================================================
# NAT Gateway + EIP
#==================================================
resource "aws_eip" "nat_eip" {
  domain = "vpc"

  tags = {
    Name = "nat-eip"
  }
}

resource "aws_nat_gateway" "nat_gw" {
  allocation_id = aws_eip.nat_eip.id
  subnet_id     = aws_subnet.public_subnet_a.id

  tags = {
    Name = "nat-gateway"
  }
}

#==================================================
# Route Tables
#==================================================
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.community_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "public-rt"
  }
}

resource "aws_route_table_association" "public_a_assoc" {
  subnet_id      = aws_subnet.public_subnet_a.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table_association" "public_c_assoc" {
  subnet_id      = aws_subnet.public_subnet_c.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.community_vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat_gw.id
  }

  tags = {
    Name = "private-rt"
  }
}

resource "aws_route_table_association" "private_a_assoc" {
  subnet_id      = aws_subnet.private_subnet_a.id
  route_table_id = aws_route_table.private_rt.id
}

resource "aws_route_table_association" "private_c_assoc" {
  subnet_id      = aws_subnet.private_subnet_c.id
  route_table_id = aws_route_table.private_rt.id
}

#==================================================
# Security Groups
#==================================================
resource "aws_security_group" "alb_sg" {
  name   = "alb-sg"
  vpc_id = aws_vpc.community_vpc.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.community_vpc.cidr_block]
  }

  tags = {
    Name = "alb-sg"
  }
}

resource "aws_security_group" "ecs_sg" {
  name        = "ecs-service-sg"
  description = "Security group for ECS services"
  vpc_id      = aws_vpc.community_vpc.id

  ingress {
    from_port       = 8082
    to_port         = 8082
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  ingress {
    from_port       = 8083
    to_port         = 8083
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "ecs-service-sg"
  }
}

resource "aws_security_group" "rds_sg" {
  name        = "rds-sg"
  description = "Security group for RDS MySQL"
  vpc_id      = aws_vpc.community_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "rds-sg"
  }
}

resource "aws_security_group_rule" "ecs_to_rds" {
  type                     = "ingress"
  from_port                = 3306
  to_port                  = 3306
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.ecs_sg.id
  security_group_id        = aws_security_group.rds_sg.id
}

#==================================================
# Load Balancer
#==================================================
resource "aws_lb" "alb" {
  name               = "community-alb"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [aws_subnet.public_subnet_a.id, aws_subnet.public_subnet_c.id]

  tags = {
    Name = "community-alb"
  }
}

# Post Service Target Group
resource "aws_lb_target_group" "post_tg" {
  name     = "post-tg"
  port     = 8082
  protocol = "HTTP"
  vpc_id   = aws_vpc.community_vpc.id

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200-399"
  }

  tags = {
    Name = "post-tg"
    Service = "post-service"
  }
}

# Comment Service Target Group
resource "aws_lb_target_group" "comment_tg" {
  name     = "comment-tg"
  port     = 8083
  protocol = "HTTP"
  vpc_id   = aws_vpc.community_vpc.id

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200-399"
  }

  tags = {
    Name = "comment-tg"
    Service = "comment-service"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS 리스너 - ACM 인증서가 미국 리전이라서 주석처리
# 리스너 패턴:
# Post Service: "/api/v1/posts", "/api/v1/posts/*"
# Comment Service: "/api/v1/comments", "/api/v1/comments/*", "/api/v1/posts/*/comments", "/health"
# resource "aws_lb_listener" "https" {
#   load_balancer_arn = aws_lb.alb.arn
#   port              = "443"
#   protocol          = "HTTPS"
#   ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2019-07"
#   # certificate_arn   = "arn:aws:acm:ap-northeast-2:245040175511:certificate/your-cert-id"
# 
#   default_action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.comment_tg.arn
#   }
# }

# Post Service Listener Rule - HTTP로 처리
# resource "aws_lb_listener_rule" "post_service" {
#   listener_arn = aws_lb_listener.https.arn
#   priority     = 100
# 
#   action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.post_tg.arn
#   }
# 
#   condition {
#     path_pattern {
#       values = ["/api/v1/posts", "/api/v1/posts/*"]
#     }
#   }
# }

# Comment Service Listener Rule - HTTPS 리스너가 주석처리되어서 주석처리
# resource "aws_lb_listener_rule" "comment_service" {
#   listener_arn = aws_lb_listener.https.arn
#   priority     = 100
# 
#   action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.comment_tg.arn
#   }
# 
#   condition {
#     path_pattern {
#       values = ["/api/v1/comments", "/api/v1/comments/*", "/api/v1/posts/*/comments", "/health"]
#     }
#   }
# }
