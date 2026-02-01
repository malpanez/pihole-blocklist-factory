#!/usr/bin/env bash
# Quick start script for Blocklist Factory

set -e

cd "$(dirname "$0")"

echo "🚀 Blocklist Factory - Quick Start"
echo "=================================="
echo ""

# Step 1: Sync Firebog
echo "📥 Step 1: Syncing Firebog catalog..."
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['sync-firebog']))"
echo ""

# Step 2: Validate
echo "✅ Step 2: Validating configuration..."
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['validate']))"
echo ""

# Step 3: Test build (optional)
read -p "Run quick test build with local test data? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧪 Running test build..."
    export BLOCKLIST_SOURCES=test
    python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['build', '--no-fetch']))"
    python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['analyze']))"
    python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['recommend']))"
    echo "📊 Test report: dist/reports/recommend.md"
    unset BLOCKLIST_SOURCES
    echo ""
fi

# Step 4: Full build
read -p "Run full build with Firebog sources? (Now optimized: 10-15 minutes) (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 Building from all sources..."
    echo "   Performance note: First run ~10-15 min (includes network fetch)"
    echo "   Subsequent runs ~4-7 min (uses cache, skips ~90% of downloads)"
    echo ""
    python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['build']))"
    
    echo "📊 Analyzing quality..."
    python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['analyze']))"
    
    echo "💡 Generating recommendations..."
    python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['recommend']))"
    
    echo ""
    echo "✨ Done!"
    echo ""
    echo "📋 Final report: cat dist/reports/recommend.md"
    echo ""
    echo "Next steps:"
    echo "1. Review dist/reports/recommend.md"
    echo "2. Copy URLs from top sources"
    echo "3. Add to Pi-hole GUI (http://pihole.local/admin → Adlists)"
    echo "4. Wait for gravity update"
else
    echo "ℹ️  To run the full build later, use:"
    echo "   python3 -c \"import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['build']))\""
fi

echo ""
echo "📖 For detailed guide, see: USAGE_GUIDE.md"
