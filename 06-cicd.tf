# ===========================
# 06-cicd.tf (GitHub 연동 + ECR 추가)
# ===========================

# ---------------------------
# 필수 변수 선언
# ---------------------------
variable "region" {
  type    = string
  default = "ap-northeast-2"
}

variable "project" {
  type    = string
  default = "comment-service"
}

variable "env" {
  type    = string
  default = "dev"
}

variable "github_owner" {
  type    = string
  default = "Everlandgo"
}

variable "github_repo" {
  type    = string
  default = "Comment_community_service"
}

variable "github_branch" {
  type    = string
  default = "main"
}

variable "eks_cluster_name" {
  type    = string
  default = "scrumptious-disco-party"
}

# ---------------------------
# 로컬 변수
# ---------------------------
locals {
  artifact_bucket_name = "artifact-${data.aws_caller_identity.current.account_id}-${var.region}"
}

data "aws_caller_identity" "current" {}

# ---------------------------
# S3 버킷 (CodePipeline 아티팩트 저장용)
# ---------------------------
resource "aws_s3_bucket" "artifacts" {
  bucket = local.artifact_bucket_name
  tags   = { Project = var.project, Env = var.env }
}

# ---------------------------
# GitHub 연결 (CodeStar Connection)
# ---------------------------
resource "aws_codestarconnections_connection" "github" {
  name          = "github-comment-service"
  provider_type = "GitHub"
}

# ---------------------------
# CodeBuild IAM Role
# ---------------------------
data "aws_iam_policy_document" "cb_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codebuild" {
  name               = "${var.project}-${var.env}-cb-role"
  assume_role_policy = data.aws_iam_policy_document.cb_trust.json
}

data "aws_iam_policy_document" "cb_policy" {
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:*"]
  }
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
  }
  statement {
    actions   = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:DescribeRepositories",
      "ecr:BatchGetImage"
    ]
    resources = ["*"]
  }
  statement {
    actions   = ["eks:DescribeCluster", "eks:ListClusters"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "cb_inline" {
  role   = aws_iam_role.codebuild.id
  name   = "cb-inline"
  policy = data.aws_iam_policy_document.cb_policy.json
}

# ---------------------------
# CodeBuild 프로젝트
# ---------------------------
resource "aws_codebuild_project" "build" {
  name         = "${var.project}-${var.env}-build"
  service_role = aws_iam_role.codebuild.arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type    = "BUILD_GENERAL1_SMALL"
    image           = "aws/codebuild/standard:7.0"
    type            = "LINUX_CONTAINER"
    privileged_mode = true

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.region
    }
    environment_variable {
      name  = "REPO_NAME"
      value = "comment-service"
    }
    environment_variable {
      name  = "APP_NAME"
      value = "comment-service"
    }
    environment_variable {
      name  = "K8S_NAMESPACE"
      value = "comment-service"
    }
    environment_variable {
      name  = "K8S_CLUSTER_NAME"
      value = var.eks_cluster_name
    }
    environment_variable {
      name  = "ACCOUNT_ID"
      value = data.aws_caller_identity.current.account_id
    }
    environment_variable {
      name  = "ECR_REPO_URI"
      value = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com/comment-service"
    }
  }

  source {
    type = "CODEPIPELINE"
  }

  logs_config {
    cloudwatch_logs {
      group_name = "/codebuild/${var.project}-${var.env}-build"
    }
  }

  tags = { Project = var.project, Env = var.env }
}

# ---------------------------
# ECR 리포지토리 생성
# ---------------------------
resource "aws_ecr_repository" "comment_service" {
  name                 = "comment-service"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project = var.project
    Env     = var.env
  }
}

output "ecr_repository_uri" {
  value = aws_ecr_repository.comment_service.repository_url
}

# ---------------------------
# CodePipeline IAM Role
# ---------------------------
data "aws_iam_policy_document" "cp_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codepipeline.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codepipeline" {
  name               = "${var.project}-${var.env}-cp-role"
  assume_role_policy = data.aws_iam_policy_document.cp_trust.json
}

data "aws_iam_policy_document" "cp_policy" {
  statement {
    actions   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn]
  }
  statement {
    actions   = ["codebuild:BatchGetBuilds", "codebuild:StartBuild"]
    resources = [aws_codebuild_project.build.arn]
  }
  statement {
    actions   = ["codestar-connections:UseConnection"]
    resources = [aws_codestarconnections_connection.github.arn]
  }
  statement {
    actions   = ["eks:DescribeCluster"]
    resources = ["arn:aws:eks:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${var.eks_cluster_name}"]
  }
}

resource "aws_iam_role_policy" "cp_inline" {
  role   = aws_iam_role.codepipeline.id
  name   = "cp-inline"
  policy = data.aws_iam_policy_document.cp_policy.json
}

# ---------------------------
# CodePipeline
# ---------------------------
resource "aws_codepipeline" "this" {
  name     = "${var.project}-${var.env}-pipeline"
  role_arn = aws_iam_role.codepipeline.arn

  artifact_store {
    type     = "S3"
    location = aws_s3_bucket.artifacts.bucket
  }

  stage {
    name = "Source"
    action {
      name             = "GithubSource"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      output_artifacts = ["source_output"]
      configuration = {
        ConnectionArn    = aws_codestarconnections_connection.github.arn
        FullRepositoryId = "${var.github_owner}/${var.github_repo}"
        BranchName       = var.github_branch
      }
    }
  }

  stage {
    name = "Build"
    action {
      name             = "DockerBuild"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["source_output"]
      output_artifacts = ["build_output"]
      configuration = {
        ProjectName = aws_codebuild_project.build.name
      }
    }
  }

  # Deploy 단계는 buildspec.yml에서 처리
  tags = { Project = var.project, Env = var.env }
}

# ---------------------------
# EKS 접근 권한 설정
# ---------------------------
# CodePipeline
resource "aws_eks_access_entry" "cp" {
  cluster_name  = var.eks_cluster_name
  principal_arn = aws_iam_role.codepipeline.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "cp_admin" {
  cluster_name  = var.eks_cluster_name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  principal_arn = aws_iam_role.codepipeline.arn
  access_scope {
    type = "cluster"
  }
}

# CodeBuild
resource "aws_eks_access_entry" "cb" {
  cluster_name  = var.eks_cluster_name
  principal_arn = aws_iam_role.codebuild.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "cb_admin" {
  cluster_name  = var.eks_cluster_name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  principal_arn = aws_iam_role.codebuild.arn
  access_scope {
    type = "cluster"
  }
}

# ---------------------------
# 출력
# ---------------------------
output "pipeline_name" {
  value = aws_codepipeline.this.name
}

output "codestar_connection_arn" {
  value = aws_codestarconnections_connection.github.arn
}
