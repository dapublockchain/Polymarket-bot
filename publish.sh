cd /Users/dapumacmini/polyarb-x
git config user.name "PolyArb-X"
git config user.email "noreply@polyarb-x.com"
git init
git remote add origin https://github.com/dapublockchain/Polymarket-bot.git
git add .
git commit -m "PolyArb-X v1.0 - Initial Release"
git branch -M main
git push -u origin main
git tag -a v1.0 -m "PolyArb-X v1.0 - Production Ready"
git push origin v1.0
