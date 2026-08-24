# Azure Cloud-Native Monitoring Demo

A small interview-ready Azure project demonstrating:

- Python/Flask application
- Docker containerization
- Terraform infrastructure on Azure
- AKS deployment
- Kubernetes probes, ConfigMap, Service, Deployment
- Prometheus metrics
- Grafana dashboards
- OpenTelemetry traces
- Azure Monitor / Application Insights
- GitHub Actions CI
- A deliberately slow endpoint for troubleshooting practice

## Architecture

GitHub -> GitHub Actions -> Docker -> Azure Container Registry -> AKS
                                               |
                                  +------------+-------------+
                                  |                          |
                              Application                Monitoring
                                  |                          |
                           OpenTelemetry              Prometheus/Grafana
                                  |
                           Azure Monitor /
                           Application Insights

## Prerequisites

- Azure CLI
- Terraform >= 1.6
- Docker
- kubectl
- Helm
- An Azure subscription
- A GitHub repository if you want CI/CD

## 1. Authenticate to Azure

```bash
az login
az account set --subscription "<SUBSCRIPTION_ID>"
az extension add --name aks-preview --upgrade
```

Create a resource group for Terraform state if desired, or use local state for the interview demo.

## 2. Provision Azure infrastructure

```bash
cd terraform
terraform init
terraform apply -var="location=westeurope"
```

The Terraform stack creates:

- Resource group
- Azure Container Registry
- Log Analytics workspace
- Application Insights
- AKS

Get outputs:

```bash
terraform output
```

Connect kubectl:

```bash
az aks get-credentials   --resource-group "$(terraform output -raw resource_group_name)"   --name "$(terraform output -raw aks_name)"   --overwrite-existing
```

## 3. Build and push the application

Log in to ACR:

```bash
az acr login --name "$(terraform output -raw acr_name)"
```

Build:

```bash
docker build -t "$(terraform output -raw acr_login_server)/monitoring-demo:local" ./../app
```

Push:

```bash
docker push "$(terraform output -raw acr_login_server)/monitoring-demo:local"
```

For a real GitHub workflow, replace `:local` with the Git SHA.

## 4. Deploy to AKS

Create the namespace:

```bash
kubectl apply -f ../kubernetes/namespace.yaml
```

Create the Application Insights secret from Terraform output:

```bash
kubectl create secret generic app-secrets   -n monitoring-demo   --from-literal=APPLICATIONINSIGHTS_CONNECTION_STRING="$(terraform output -raw application_insights_connection_string)"
```

Update `kubernetes/deployment.yaml` so the image points to your ACR image, then:

```bash
kubectl apply -f ../kubernetes/configmap.yaml
kubectl apply -f ../kubernetes/deployment.yaml
kubectl apply -f ../kubernetes/service.yaml
```

Check:

```bash
kubectl get pods -n monitoring-demo
kubectl get svc -n monitoring-demo
kubectl logs -n monitoring-demo deploy/monitoring-demo
```

## 5. Install Prometheus and Grafana

This demo uses the community kube-prometheus-stack Helm chart.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack   --namespace monitoring   --create-namespace   -f ../monitoring/prometheus-values.yaml
```

The values file enables Prometheus to scrape the application's `/metrics` endpoint.

Get Grafana credentials:

```bash
kubectl get secret monitoring-grafana   -n monitoring   -o jsonpath="{.data.admin-password}" | base64 --decode; echo
```

Port-forward Grafana:

```bash
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
```

Open http://localhost:3000 and log in as `admin`.

## 6. Enable Azure Monitor managed Prometheus

For an Azure-native production setup, Azure Monitor managed Prometheus can collect metrics without running a full Prometheus server.

After Terraform creates the workspace:

```bash
az aks update   --resource-group "$(terraform output -raw resource_group_name)"   --name "$(terraform output -raw aks_name)"   --enable-azure-monitor-metrics   --azure-monitor-workspace-resource-id "$(terraform output -raw monitor_workspace_resource_id)"
```

This project keeps the in-cluster Prometheus/Grafana deployment because it is easy to demonstrate locally. In an interview, explain that you understand both models and would normally choose Azure managed services where they reduce operational overhead.

## 7. Exercise the application

Forward the service:

```bash
kubectl port-forward svc/monitoring-demo 8080:80 -n monitoring-demo
```

Then:

```bash
curl http://localhost:8080/
curl http://localhost:8080/health
curl http://localhost:8080/metrics
curl http://localhost:8080/slow
```

Generate traffic:

```bash
for i in $(seq 1 50); do curl -s http://localhost:8080/ > /dev/null; done
```

Generate slow requests:

```bash
for i in $(seq 1 20); do curl -s http://localhost:8080/slow > /dev/null; done
```

## 8. Interview troubleshooting story

1. A latency alert fires.
2. Grafana shows elevated request latency.
3. Prometheus identifies `/slow` as the endpoint with the highest duration.
4. Application logs confirm the slow path.
5. OpenTelemetry traces show the request taking ~2 seconds.
6. The engineer identifies the intentional delay.
7. The delay is removed or reduced.
8. Traffic is generated again and the latency metric returns to normal.

Useful commands:

```bash
kubectl get pods -n monitoring-demo
kubectl describe pod -n monitoring-demo <POD>
kubectl logs -n monitoring-demo deploy/monitoring-demo
kubectl top pods -n monitoring-demo
kubectl get events -n monitoring-demo --sort-by=.lastTimestamp
```

## Interview talking points

### Why Terraform?

Infrastructure becomes reproducible, reviewable, and version controlled. A second environment can be created from the same code with different variables.

### Why Kubernetes?

The application is packaged as a container and deployed declaratively. Kubernetes handles scheduling, service discovery, health checks, and rolling updates.

### Why Prometheus?

Prometheus is well suited to time-series metrics and Kubernetes. The application exposes a standard `/metrics` endpoint.

### Why Grafana?

Grafana provides dashboards and alerting over Prometheus metrics.

### Why OpenTelemetry?

It provides vendor-neutral instrumentation for traces and metrics. The same instrumentation can later export to another observability backend.

### Why Azure Monitor?

Azure Monitor integrates logs, metrics, and application telemetry with Azure resources. Application Insights provides application-level observability.

### What would you improve for production?

- Private AKS cluster and private endpoints
- Workload Identity instead of static credentials
- Azure Key Vault + CSI driver
- ACR vulnerability scanning and image signing
- Network policies
- Resource requests/limits and PodDisruptionBudgets
- Horizontal Pod Autoscaler
- GitHub OIDC federation instead of long-lived Azure secrets
- Separate Terraform state per environment
- Azure Managed Prometheus + Azure Managed Grafana
- Centralized alert rules and SLOs
- Terraform modules and policy-as-code
