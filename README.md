# 🚀 Mini Project — 2-Tier Flask + MySQL on EKS

A production-grade two-tier web application built with Flask and MySQL, deployed on AWS EKS with a real-time Kubernetes monitoring dashboard and full DevOps tooling.

[![CI](https://github.com/Rohit-Kiran24/mini-project-2-tier-app/actions/workflows/ci.yml/badge.svg)](https://github.com/Rohit-Kiran24/mini-project-2-tier-app/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9-blue)
![Flask](https://img.shields.io/badge/flask-2.0.1-lightgrey)
![MySQL](https://img.shields.io/badge/mysql-5.7-orange)
![Kubernetes](https://img.shields.io/badge/kubernetes-EKS-326CE5)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen)

---

## 📸 Dashboard

A unified real-time dashboard showing live messages, pod health, CPU/memory load, and cluster events — all updating via Server-Sent Events (no polling).

---

## 🏗️ Architecture
```
Browser
  │
  ▼
Flask App (Gunicorn + Gevent, 4 workers)
  │               │
  ▼               ▼
MySQL 5.7     /metrics ──► Prometheus ──► Grafana
(StatefulSet)
  │
  ▼
Fluent Bit ──► AWS CloudWatch Logs
```

---

## ✨ Features

| Feature | Detail |
|---------|--------|
| Real-time dashboard | Server-Sent Events — zero polling overhead |
| Production server | Gunicorn + Gevent workers |
| DB connection pool | SQLAlchemy QueuePool, pool_pre_ping, pool_recycle |
| Rate limiting | 20 req/min on POST + DELETE via Flask-Limiter |
| Security headers | CORS + CSP via flask-talisman |
| Prometheus metrics | `/metrics` endpoint via prometheus-flask-exporter |
| DB startup retry | Exponential backoff, 10 attempts max |
| Health probes | Liveness `/api/health` + Readiness `/api/ready` |
| Autoscaling | HPA — min 1, max 4 pods at 70% CPU |
| Log shipping | Fluent Bit DaemonSet → CloudWatch |
| CI/CD | GitHub Actions + Jenkins pipeline |
| Security scanning | Trivy on every build |
| RBAC | ServiceAccount + Role + RoleBinding for k8s API access |
| NetworkPolicy | MySQL only accessible from Flask pods |
| Pagination | `?page=1&limit=20` on messages API |

---

## 📁 Project Structure
```
mini-project-2-tier-app/
├── app.py                        # Flask application (API + SSE + k8s client)
├── templates/
│   └── index.html                # Real-time dashboard UI
├── tests/
│   └── test_app.py               # pytest unit tests
├── k8s/
│   ├── two-tier-app-deployment.yml  # Flask Deployment
│   ├── two-tier-app-svc.yml         # Flask Service
│   ├── mysql-deployment.yml         # MySQL StatefulSet
│   ├── mysql-svc.yml                # MySQL Service
│   ├── flask-rbac.yaml              # RBAC for k8s API access
│   ├── flask-hpa.yaml               # Horizontal Pod Autoscaler
│   ├── mysql-secret.yaml            # DB credentials Secret
│   ├── mysql-pvc.yml                # Persistent Volume Claim
│   ├── mysql-netpol.yaml            # NetworkPolicy
│   ├── fluent-bit.yaml              # Log shipping DaemonSet
│   └── prometheus-values.yaml       # kube-prometheus-stack Helm values
├── flask-app-chart/              # Helm chart for Flask app
├── mysql-chart/                  # Helm chart for MySQL
├── eks-manifests/                # EKS-specific manifests
├── .github/workflows/ci.yml      # GitHub Actions CI
├── Dockerfile                    # Multi-stage ready
├── docker-compose.yml            # Local development
├── Jenkinsfile                   # Jenkins CI/CD pipeline
├── .env.example                  # Environment variable template
└── .dockerignore
```

---

## 🚀 Quick Start (Local)
```bash
# Clone
git clone https://github.com/Rohit-Kiran24/mini-project-2-tier-app.git
cd mini-project-2-tier-app

# Copy env
cp .env.example .env

# Run
docker-compose up --build

# Open http://localhost:5000
```

---

## ☸️ EKS Deployment
```bash
# 1. Secrets + Storage
kubectl apply -f k8s/mysql-secret.yaml
kubectl apply -f k8s/mysql-pv.yml
kubectl apply -f k8s/mysql-pvc.yml

# 2. MySQL
kubectl apply -f k8s/mysql-deployment.yml
kubectl apply -f k8s/mysql-svc.yml

# 3. Flask App
kubectl apply -f k8s/flask-rbac.yaml
kubectl apply -f k8s/two-tier-app-deployment.yml
kubectl apply -f k8s/two-tier-app-svc.yml

# 4. Autoscaling + Security
kubectl apply -f k8s/flask-hpa.yaml
kubectl apply -f k8s/mysql-netpol.yaml

# 5. Monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack \
  -f k8s/prometheus-values.yaml \
  --namespace monitoring --create-namespace

# 6. Log shipping
kubectl apply -f k8s/fluent-bit.yaml
```

---

## 🎯 Live Demo Commands
```bash
# Watch pods in real time
kubectl get pods -w

# Trigger pod crash (watch dashboard go red → green)
kubectl delete pod <flask-pod-name> --force

# Scale up (watch 3 pods appear on dashboard)
kubectl scale deployment two-tier-app --replicas=3

# Check HPA
kubectl get hpa

# View metrics
curl http://<EXTERNAL-IP>:5000/metrics
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard UI |
| GET | `/api/messages?page=1&limit=20` | Paginated messages |
| POST | `/api/messages` | Post a message |
| DELETE | `/api/messages/<id>` | Delete a message |
| GET | `/api/pods` | Live pod status |
| POST | `/api/spike` | Trigger 10s CPU spike |
| GET | `/api/health` | Liveness probe |
| GET | `/api/ready` | Readiness probe |
| GET | `/api/stream` | SSE stream (pod + message updates) |
| GET | `/metrics` | Prometheus metrics |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.9, Flask 2.0.1 |
| Database | MySQL 5.7, SQLAlchemy 2.0 |
| Server | Gunicorn + Gevent |
| Container | Docker, Docker Compose |
| Orchestration | Kubernetes on AWS EKS |
| CI/CD | GitHub Actions, Jenkins |
| Monitoring | Prometheus, Grafana |
| Logging | Fluent Bit → AWS CloudWatch |
| Security | Trivy, flask-talisman, NetworkPolicy, RBAC |

---

## 👨‍💻 Author

**Rohit Kiran** — [GitHub](https://github.com/Rohit-Kiran24) this one 
