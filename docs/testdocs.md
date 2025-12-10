Server Endpoint 
https://api.pathofexile.com

Currency Exchange
Required scope: service:cxapi

Get Exchange Markets 
GET /currency-exchange[/<realm>][/<id>]

realm can either be xbox, sony, or poe2. If omitted then the PoE1 PC realm is assumed (optional)
id is a unix timestamp code received from this endpoint. If none is provided then first hour of history is assumed

Returns:
This endpoint allows you to view aggregate Currency Exchange trade history, grouped into hourly digests. Each market (pair of two currencies) that has seen activity in the requested hour will be returned.
Note that the responses from this endpoint are purely historical and that there isn't any way to get data from the current hour.
If the next_change_id is the same unix timestamp as the one you passed in, then you have reached the current end of the stream. You should wait until the next hourly boundary before calling this endpoint again.

Key	Type	Extra Information
next_change_id	uint	unix timestamp truncated to the hour
markets	array of object	
↳ league	string	
↳ market_id	string	common currency code for each pair separated by a pipe. Example: chaos|divine
↳ volume_traded	dictionary of uint	the keys are the market currencies. Example: chaos
↳ lowest_stock	dictionary of uint	
↳ highest_stock	dictionary of uint	
↳ lowest_ratio	dictionary of uint	
↳ highest_ratio	dictionary of uint	

Be aware that we may, at a later date, remove old history entries.