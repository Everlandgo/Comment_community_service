# ===========================
# 06-cicd.tf (GitHub 연결 + ECR + CodeBuild + CodePipeline + EKS 배포)
# ===========================

# ---------------------------
# 변수 선언
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

# EKS 관련 변수
variable "eks_cluster_name" {
  type    = string
  default = "happy-synth-ladybug"
}

variable "k8s_namespace" {
  type    = string
  default = "comment-service"
}

# ---------------------------
# S3 버킷 (아티팩트 저장용)
# ---------------------------
data "aws_s3_bucket" "artifacts" {
  bucket = "karina-winter"
}

# ---------------------------
# GitHub 연결
# ---------------------------
data "aws_codestarconnections_connection" "github" {
  arn = "arn:aws:codestar-connections:ap-northeast-2:245040175511:connection/8eb2b6fd-9dd2-4214-994e-a0b24f3fe2c6"
}

data "aws_caller_identity" "current" {}

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
    sid     = "CloudWatchLogs"
    actions = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:*"
    ]
  }

  statement {
    sid     = "S3Access"
    actions = ["s3:GetObject","s3:PutObject","s3:ListBucket"]
    resources = [
      "arn:aws:s3:::${data.aws_s3_bucket.artifacts.id}",
      "arn:aws:s3:::${data.aws_s3_bucket.artifacts.id}/*"
    ]
  }

  statement {
    sid = "ECRAccess"
    actions = [
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
    sid = "EKSAccess"
    actions = [
      "eks:DescribeCluster",
      "eks:ListClusters",
      "eks:UpdateKubeconfig"
    ]
    resources = [
      "arn:aws:eks:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${var.eks_cluster_name}"
    ]
  }

  statement {
    sid     = "IAMPassRole"
    actions = ["iam:PassRole"]
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
      name  = "ECR_REPO_URI"
      value = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com/comment-service"
    }

    environment_variable {
      name  = "K8S_CLUSTER_NAME"
      value = var.eks_cluster_name
    }

    environment_variable {
      name  = "K8S_NAMESPACE"
      value = var.k8s_namespace
    }

    environment_variable {
      name  = "REPO_NAME"
      value = "comment-service"
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

  tags = {
    Project = var.project
    Env     = var.env
  }
}

# ---------------------------
# ECR 리포지토리
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
    sid     = "S3Objects"
    actions = ["s3:GetObject","s3:GetObjectVersion","s3:PutObject","s3:DeleteObject"]
    resources = ["arn:aws:s3:::${data.aws_s3_bucket.artifacts.id}/*"]
  }

  statement {
    sid     = "S3List"
    actions = ["s3:ListBucket","s3:GetBucketLocation"]
    resources = ["arn:aws:s3:::${data.aws_s3_bucket.artifacts.id}"]
  }

  statement {
    sid       = "CodeBuildStart"
    actions   = ["codebuild:BatchGetBuilds","codebuild:StartBuild"]
    resources = [aws_codebuild_project.build.arn]
  }

  statement {
    sid       = "UseCodeStarConnection"
    actions   = ["codestar-connections:UseConnection"]
    resources = [data.aws_codestarconnections_connection.github.arn]
  }

  statement {
    sid     = "EKSAccessForPipeline"
    actions = ["eks:DescribeCluster","eks:ListClusters","eks:AccessKubernetesApi"]
    resources = [
      "arn:aws:eks:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${var.eks_cluster_name}"
    ]
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
    location = data.aws_s3_bucket.artifacts.bucket
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
        ConnectionArn    = data.aws_codestarconnections_connection.github.arn
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

  tags = {
    Project = var.project
    Env     = var.env
  }
}

# ---------------------------
# EKS RBAC 매핑 (CodeBuild/CodePipeline)
# ---------------------------
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
  value = data.aws_codestarconnections_connection.github.arn
}

output "codebuild_role_arn" {
  value = aws_iam_role.codebuild.arn
}

output "codepipeline_role_arn" {
  value = aws_iam_role.codepipeline.arn
}
