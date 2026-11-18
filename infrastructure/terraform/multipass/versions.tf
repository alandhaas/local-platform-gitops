terraform {
  required_version = ">= 1.10.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.6"
    }

    multipass = {
      source  = "todoroff/multipass"
      version = "~> 2.1"
    }
  }
}

provider "multipass" {}
