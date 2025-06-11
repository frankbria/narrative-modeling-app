# Production Deployment Guide

## 🚀 Overview

This guide covers deploying the Narrative Modeling App to production using Docker containers, nginx reverse proxy, and comprehensive monitoring.

## 🏗️ Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    Nginx    │────│  Frontend   │────│   Backend   │
│ (Port 80)   │    │ (Port 3000) │    │ (Port 8000) │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │                   └───────┬───────────┘
       │                           │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   MongoDB   │    │    Redis    │    │ MCP Server  │
│ (Port 27017)│    │ (Port 6379) │    │(Port 10000) │
└─────────────┘    └─────────────┘    └─────────────┘
```

## 📋 Prerequisites

1. **Docker & Docker Compose**
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   
   # Install Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

2. **Server Requirements**
   - Minimum: 4GB RAM, 2 CPU cores, 50GB storage
   - Recommended: 8GB RAM, 4 CPU cores, 100GB storage
   - OS: Ubuntu 20.04+ or similar Linux distribution

3. **External Services**
   - MongoDB Atlas (or self-hosted MongoDB)
   - AWS S3 bucket for file storage
   - OpenAI API key
   - Clerk authentication keys
   - Domain name with SSL certificate

## 🔧 Setup Instructions

### 1. Clone Repository

```bash
git clone https://github.com/your-org/narrative-modeling-app.git
cd narrative-modeling-app
```

### 2. Environment Configuration

```bash
# Copy environment template
cp .env.production.example .env.prod

# Edit environment variables
nano .env.prod
```

**Required Environment Variables:**

```bash
# Database
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/narrative_modeling
MONGODB_DB=narrative_modeling
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=your_strong_password

# Redis
REDIS_URL=redis://redis:6379
REDIS_PASSWORD=your_redis_password

# AWS
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=your-bucket-name

# OpenAI
OPENAI_API_KEY=sk-your-openai-key

# Clerk Auth
CLERK_SECRET_KEY=sk_live_your_clerk_secret
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_your_clerk_public_key

# Application
ENVIRONMENT=production
NODE_ENV=production
NEXT_PUBLIC_API_URL=https://your-domain.com
```

### 3. SSL Certificate Setup (Optional but Recommended)

```bash
# Create SSL directory
mkdir -p nginx/ssl

# Option 1: Let's Encrypt (recommended)
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem

# Option 2: Self-signed (development only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem
```

### 4. Deploy Application

```bash
# Make deployment script executable
chmod +x scripts/deploy-production.sh

# Run deployment
./scripts/deploy-production.sh
```

## 📊 Monitoring & Management

### Check Deployment Status

```bash
# View all services
./scripts/deploy-production.sh status

# View specific service logs
./scripts/deploy-production.sh logs backend
./scripts/deploy-production.sh logs frontend
```

### Health Checks

- **Application**: http://your-domain.com/health
- **Backend API**: http://your-domain.com/api/health
- **Individual Services**: `docker-compose -f docker-compose.prod.yml ps`

### Performance Monitoring

```bash
# View resource usage
docker stats

# View system metrics
htop
df -h
free -h
```

## 🔄 Maintenance Tasks

### Database Backup

```bash
# Manual backup
docker-compose -f docker-compose.prod.yml exec mongodb mongodump --archive > backup/mongodb_$(date +%Y%m%d).archive

# Automated backup (add to crontab)
0 2 * * * cd /path/to/app && docker-compose -f docker-compose.prod.yml exec -T mongodb mongodump --archive > backup/mongodb_$(date +\%Y\%m\%d).archive
```

### Log Rotation

```bash
# Setup logrotate
sudo nano /etc/logrotate.d/narrative-modeling

# Content:
/path/to/app/nginx/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 root root
    postrotate
        docker-compose -f /path/to/app/docker-compose.prod.yml exec nginx nginx -s reload
    endscript
}
```

### Updates & Deployments

```bash
# Pull latest changes
git pull origin main

# Redeploy
./scripts/deploy-production.sh

# Rollback if needed
./scripts/deploy-production.sh rollback
```

## 🛡️ Security Checklist

- [ ] SSL/TLS certificates configured
- [ ] Strong passwords for all services
- [ ] Firewall configured (ports 80, 443 only)
- [ ] Regular security updates
- [ ] Database access restricted
- [ ] API keys rotated regularly
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] Security headers set

## 🚨 Troubleshooting

### Common Issues

1. **Service Won't Start**
   ```bash
   # Check logs
   docker-compose -f docker-compose.prod.yml logs service_name
   
   # Check resources
   docker stats
   df -h
   ```

2. **Database Connection Issues**
   ```bash
   # Test MongoDB connection
   docker-compose -f docker-compose.prod.yml exec backend python -c "
   import os
   from motor.motor_asyncio import AsyncIOMotorClient
   client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
   print('MongoDB connection successful')
   "
   ```

3. **Frontend Build Issues**
   ```bash
   # Rebuild frontend
   docker-compose -f docker-compose.prod.yml build --no-cache frontend
   ```

4. **SSL Certificate Issues**
   ```bash
   # Check certificate validity
   openssl x509 -in nginx/ssl/cert.pem -text -noout
   
   # Test SSL
   curl -vI https://your-domain.com
   ```

### Performance Issues

1. **High Memory Usage**
   ```bash
   # Increase Docker memory limits in docker-compose.prod.yml
   deploy:
     resources:
       limits:
         memory: 2G
   ```

2. **Slow Database Queries**
   ```bash
   # Check MongoDB slow queries
   docker-compose -f docker-compose.prod.yml exec mongodb mongo --eval "db.setProfilingLevel(2, {slowms: 100})"
   ```

3. **High CPU Usage**
   ```bash
   # Scale services
   docker-compose -f docker-compose.prod.yml up -d --scale backend=3
   ```

## 📈 Scaling

### Horizontal Scaling

```yaml
# docker-compose.prod.yml
backend:
  deploy:
    replicas: 3
  
nginx:
  # Add load balancing configuration
```

### Vertical Scaling

```yaml
# Increase resource limits
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

## 🔧 Advanced Configuration

### Custom Domains

1. Update nginx configuration
2. Add SSL certificates
3. Update environment variables
4. Redeploy application

### CDN Integration

```nginx
# Add to nginx.conf
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    proxy_pass https://your-cdn.cloudfront.net;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### Monitoring Integration

```yaml
# Add to docker-compose.prod.yml
prometheus:
  image: prom/prometheus
  ports: ["9090:9090"]
  
grafana:
  image: grafana/grafana
  ports: ["3001:3000"]
```

## 📞 Support

For production support issues:

1. Check logs first: `./scripts/deploy-production.sh logs`
2. Review this documentation
3. Check GitHub issues
4. Contact support team

## 🔄 Backup & Recovery

### Full Backup

```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backup/$DATE"

mkdir -p "$BACKUP_DIR"

# Database backup
docker-compose -f docker-compose.prod.yml exec -T mongodb mongodump --archive > "$BACKUP_DIR/mongodb.archive"

# Code backup
tar -czf "$BACKUP_DIR/application.tar.gz" --exclude=node_modules --exclude=.git .

# Environment backup
cp .env.prod "$BACKUP_DIR/"

echo "Backup completed: $BACKUP_DIR"
```

### Recovery

```bash
# Restore database
docker-compose -f docker-compose.prod.yml exec -T mongodb mongorestore --archive < backup/latest/mongodb.archive

# Restore application
tar -xzf backup/latest/application.tar.gz

# Redeploy
./scripts/deploy-production.sh
```

---

**🎉 Your Narrative Modeling App is now ready for production!**