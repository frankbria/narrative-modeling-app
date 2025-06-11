#!/bin/bash
# Script to migrate from Poetry to uv package manager

set -e

echo "🚀 Starting migration from Poetry to uv..."

# Function to migrate a project
migrate_project() {
    local project_dir=$1
    local project_name=$2
    
    echo ""
    echo "📦 Migrating $project_name in $project_dir..."
    
    cd "$project_dir"
    
    # Backup original files
    if [ -f "pyproject.toml" ]; then
        cp pyproject.toml pyproject.toml.poetry-backup
        echo "  ✓ Backed up original pyproject.toml"
    fi
    
    if [ -f "poetry.lock" ]; then
        cp poetry.lock poetry.lock.backup
        echo "  ✓ Backed up poetry.lock"
    fi
    
    # Replace pyproject.toml with new version
    if [ -f "pyproject.toml.new" ]; then
        mv pyproject.toml.new pyproject.toml
        echo "  ✓ Updated pyproject.toml for uv"
    fi
    
    # Create virtual environment with uv
    echo "  📥 Creating virtual environment with uv..."
    uv venv --python 3.11
    
    # Install dependencies
    echo "  📥 Installing dependencies..."
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        .venv/Scripts/activate && uv pip install -e ".[dev]"
    else
        source .venv/bin/activate && uv pip install -e ".[dev]"
    fi
    
    echo "  ✅ $project_name migration complete!"
    
    cd - > /dev/null
}

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Migrate backend
migrate_project "apps/backend" "Backend"

# Migrate MCP server
migrate_project "apps/mcp" "MCP Server"

echo ""
echo "🎉 Migration complete!"
echo ""
echo "📝 Next steps:"
echo "1. Test that everything works:"
echo "   cd apps/backend && source .venv/bin/activate && python -m app.main"
echo "   cd apps/mcp && source .venv/bin/activate && python main.py"
echo ""
echo "2. Commit the changes:"
echo "   git add -A"
echo "   git commit -m 'Migrate from Poetry to uv package manager'"
echo ""
echo "3. Update your IDE to use the new .venv directories"
echo ""
echo "4. You can now delete the backup files after confirming everything works:"
echo "   find apps -name '*.poetry-backup' -delete"
echo "   find apps -name 'poetry.lock*' -delete"