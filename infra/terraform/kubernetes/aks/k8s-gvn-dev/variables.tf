variable "resource_group_location" {
    type        = string
    default     = "eastus2"
}

variable "resource_group_name_prefix" {
    type        = string
    default     = "rg-k8s-gvn-dev"
}

variable "cluster_name" {
    type        = string
    default     = "k8s-gvn-dev"
}

variable "dns_prefix" {
    type        = string
    default     = "dns-k8s-gvn-dev"
}

variable "vm_size" {
    type        = string
    default     = "Standard_DS2_v2"
}

variable "node_count" {
    type        = number
    default     = 2
}

variable "msi_id" {
    type        = string
    default     = null
}