provider "aws" {
  region = "ap-northeast-2"
}

# =========================
# IAM Roles
# =========================

    # =========================
    # EKS Cluster Role
    # =========================
resource "aws_iam_role" "eks_cluster_role" {
  name = "private-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Effect = "Allow"
      Sid    = ""
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_role_attach" {
  role       = aws_iam_role.eks_cluster_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

    # =========================
    # EKS Node Role
    # =========================
resource "aws_iam_role" "eks_node_role" {
  name = "private-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_node_policy_attach" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_cni_attach" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "eks_ecr_attach" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "eks_ssm_attach" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# =========================
# EKS Cluster
# =========================

resource "aws_eks_cluster" "private_eks" {
  name     = "private-eks-cluster"
  role_arn = aws_iam_role.eks_cluster_role.arn
  version  = "1.33"

  vpc_config {
    subnet_ids              = ["subnet-06d476d602aee24cd", "subnet-0bbd420e44ca49442"]
    endpoint_private_access = true
    endpoint_public_access  = false
    public_access_cidrs     = []
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_role_attach
  ]
}

# =========================
# Node Group
# =========================

resource "aws_eks_node_group" "private_node_group" {
  cluster_name    = aws_eks_cluster.private_eks.name
  node_group_name = "private-node-group"
  node_role_arn   = aws_iam_role.eks_node_role.arn
  subnet_ids      = ["subnet-06d476d602aee24cd", "subnet-0bbd420e44ca49442"]
  scaling_config {
    desired_size = 4
    max_size     = 4
    min_size     = 2
  }

  remote_access {
    ec2_ssh_key = null
    source_security_group_ids = [] # SSM만 허용
  }

  instance_types = ["t3.medium"]

  capacity_type = "ON_DEMAND"

  depends_on = [
    aws_iam_role_policy_attachment.eks_node_policy_attach,
    aws_iam_role_policy_attachment.eks_cni_attach,
    aws_iam_role_policy_attachment.eks_ecr_attach,
    aws_iam_role_policy_attachment.eks_ssm_attach
  ]
}
