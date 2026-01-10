#!/bin/bash
# Export Firebase Auth users from all app projects

echo "🔥 Exporting Firebase users from all projects..."
echo "================================================"
echo ""

# Create exports directory
mkdir -p firebase_exports

# Map project IDs to app names
declare -A PROJECT_MAP=(
    ["audio-recorder-microphone"]="Smart Notes"
    ["girlfriend-app-cupid"]="Ai Girlfriend"
    ["redflagscanner"]="Red Flag Scanner"
    ["breakuptherapy-e7dc0"]="Fresh Start"
    ["soulplan-dateplanner"]="SoulPlan"
    ["petmealai"]="PupShape"
    ["predictify-3f30d"]="Predictify"
)

# Export from each project
for project_id in "${!PROJECT_MAP[@]}"; do
    app_name="${PROJECT_MAP[$project_id]}"
    echo "📱 Exporting from: $app_name ($project_id)"
    
    firebase auth:export "firebase_exports/${project_id}_users.json" \
        --project "$project_id" \
        --format=JSON 2>&1
    
    if [ $? -eq 0 ]; then
        echo "   ✅ Exported successfully"
    else
        echo "   ⚠️  Export failed or no users"
    fi
    echo ""
done

echo "================================================"
echo "✅ Export complete!"
echo ""
echo "📁 Files created in: firebase_exports/"
echo ""
echo "🚀 Next step: Run the format script"
echo "   python3 scripts/format_firebase_exports.py"
