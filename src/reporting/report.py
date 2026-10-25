"""Presentation of published gold facts; no cost model, imputation, or forecasts."""
from decimal import Decimal
from html import escape
import pandas as pd
import streamlit as st
from reporting.business import summarize_areas, summarize_days, business_insights
from storage.object_store import optional_json, parquet_frame

st.set_page_config(page_title='Chicago Taxi | Revenue, clearly.', page_icon='🚕', layout='wide')
st.markdown("""
<style>
.stApp {background:#f3f5f9;color:#17263b}
.block-container {max-width:1400px;padding-top:2rem;padding-bottom:3rem}
h1,h2,h3 {letter-spacing:-.025em}
[data-testid="stMetric"] {background:white;border:1px solid #e1e7ef;border-radius:15px;padding:18px 20px;box-shadow:0 3px 12px rgba(20,40,70,.035)}
[data-testid="stMetricLabel"] {color:#586a80}
[data-testid="stMetricValue"] {color:#102a43;font-weight:700}
[data-baseweb="tab-list"] {gap:18px;border-bottom:1px solid #dbe3ec;margin:12px 0 20px}
[data-baseweb="tab"] {font-size:16px}
[data-testid="stButton"] button {border-radius:10px;border-color:#d0dae6}
.hero {background:#102a43;border-radius:22px;padding:32px 36px;margin-bottom:22px;border-top:5px solid #f4bd54}
.eyebrow {font-size:12px;font-weight:700;letter-spacing:.15em;color:#f4bd54;margin-bottom:12px}
.hero h1 {font-size:38px;line-height:1.12;color:white!important;margin:0 0 12px;padding:0}
.hero p {font-size:16px;line-height:1.6;color:#d3dfeb;margin:0;max-width:850px}
.pill {display:inline-block;background:#25435d;color:#e6edf5;font-size:12px;padding:6px 12px;border-radius:30px;margin:17px 8px 0 0}
.note {background:#fff8e9;border-left:4px solid #e9ae35;border-radius:0 10px 10px 0;padding:13px 17px;margin:18px 0;color:#584523;line-height:1.6}
.insight {background:white;border:1px solid #e0e7ef;border-left:4px solid #24877f;border-radius:0 12px 12px 0;padding:16px 20px;margin:12px 0;line-height:1.65}
.section-kicker {font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:#60748b;font-weight:700;margin:28px 0 10px}
</style>
""", unsafe_allow_html=True)

control, metadata_space = st.columns([1, 4])
with control:
    if st.button('↻ Refresh results', use_container_width=True):
        st.cache_data.clear()
try:
    published = optional_json('published/latest.json')
except Exception:
    st.info('The data store is starting. Wait a moment, then refresh.')
    st.stop()
if not published:
    st.title('Chicago Taxi · Revenue, clearly.')
    st.info('No results have been published. Trigger chicago_taxi_trust in Airflow, wait for all five tasks to succeed, then refresh.')
    st.stop()

@st.cache_data
def load_tables(prefix):
    return parquet_frame(prefix + '/daily/'), parquet_frame(prefix + '/areas/')

try:
    daily, areas = load_tables(published['prefix'])
    summary = summarize_areas(areas.to_dict('records'), min_trips=1)
    days = summarize_days(daily.to_dict('records'))
    daily_amount = sum((Decimal(str(v)) for v in daily['recorded_trip_total_usd']), Decimal('0'))
    if daily_amount != summary['total_revenue_usd']:
        raise ValueError('Published daily and area revenue totals disagree.')
except Exception as exc:
    st.error(f'Could not verify or read the published metrics: {exc}')
    st.stop()

silver, quality = published['silver'], published['silver']['metrics']
ranked = summary['ranking']
known_coverage = (100 - summary['unknown_revenue_share_pct']
                  if summary['unknown_revenue_share_pct'] is not None else None)
with metadata_space:
    st.caption('Published: ' + published['published_at'])
st.markdown(
    '<div class="hero"><div class="eyebrow">CHICAGO TAXI / PUBLISHED DATA</div>'
    '<h1>Revenue, clearly.</h1>'
    '<p>See which pickup areas generated the most recorded money, '
    'how that compares with trip volume, and exactly what the data covers.</p>'
    f'<span class="pill">{escape(silver["start"])} → {escape(silver["end_exclusive"])} · end excluded</span>'
    '<span class="pill">Accepted trips only</span><span class="pill">USD</span></div>',
    unsafe_allow_html=True,
)
a, b, c, d = st.columns(4)
a.metric('Total recorded revenue', f"${summary['total_revenue_usd']:,.2f}",
         help='Sum of accepted source trip_total values, including trips with unknown pickup areas.')
b.metric('Accepted trips', f"{quality['accepted']:,}")
c.metric('Average recorded amount / trip', f"${days['average_recorded_total_usd']:,.2f}",
         help='Total accepted recorded amount divided by accepted trips, not an average of area averages.')
d.metric('Revenue with a known pickup area',
         f'{known_coverage:.1f}%' if known_coverage is not None else 'N/A',
         help='Known-area recorded revenue divided by total accepted recorded revenue.')

st.markdown('<div class="section-kicker">What stands out in this period</div>', unsafe_allow_html=True)
def leader_label(rows):
    if not rows:
        return 'Unavailable'
    return 'Area ' + rows[0]['pickup_area'] + (f' (+{len(rows)-1} tied)' if len(rows) > 1 else '')

rev_leads = [r for r in ranked if r['revenue_rank'] == 1]
trip_leads = [r for r in ranked if r['trip_rank'] == 1]
yield_rows = summary['eligible_yield_ranking']
yield_leads = [r for r in yield_rows if r['average_recorded_total_usd'] == yield_rows[0]['average_recorded_total_usd']] if yield_rows else []
a, b, c = st.columns(3)
a.metric('Highest recorded revenue', leader_label(rev_leads),
         help='Known pickup areas only. Full rankings and ties appear below.')
b.metric('Most accepted trips', leader_label(trip_leads))
c.metric('Highest observed amount / trip', leader_label(yield_leads),
         help='Includes every known area with at least one accepted trip. Inspect sample counts below.')
if rev_leads:
    st.caption(f"Revenue leader: ${rev_leads[0]['recorded_trip_total_usd']:,.2f} from {rev_leads[0]['trip_count']:,} accepted trips. Area codes are source community-area identifiers.")

if summary['unknown_trip_count']:
    unknown_share = summary['unknown_revenue_share_pct']
    share_text = f' ({unknown_share:.1f}% of the total)' if unknown_share is not None else ''
    st.markdown(
        f'<div class="note"><strong>Location coverage:</strong> '
        f'{summary["unknown_trip_count"]:,} accepted trips and '
        f'${summary["unknown_revenue_usd"]:,.2f}{share_text} have no known pickup area. '
        'They count in the headline totals, but cannot be placed in the area rankings.</div>',
        unsafe_allow_html=True,
    )

def chart(frame, label, value, color, money=False):
    data = frame[[label, value]].copy()
    data[label] = data[label].astype(str)
    data[value] = data[value].astype(float)
    axis = {'title': value}
    if money:
        axis['format'] = '$,.0f'
    st.vega_lite_chart(data, {
        'height': max(210, min(len(data), 10) * 29),
        'mark': {'type': 'bar', 'color': color, 'cornerRadiusEnd': 4},
        'encoding': {
            'y': {'field': label, 'type': 'nominal', 'sort': '-x', 'axis': {'title': None}},
            'x': {'field': value, 'type': 'quantitative', 'axis': axis},
            'tooltip': [
                {'field': label, 'type': 'nominal'},
                {'field': value, 'type': 'quantitative', 'format': '$,.2f' if money else ',.0f'},
            ],
        },
        'config': {'view': {'stroke': None}, 'axis': {'gridColor': '#e7edf4', 'labelColor': '#53687f'}},
    }, use_container_width=True)

area_tab, day_tab, trust_tab = st.tabs(['Revenue by area', 'Daily performance', 'Data quality & definitions'])
with area_tab:
    st.subheader('The revenue ranking')
    st.caption('All dates in the published interval combined. Known pickup areas only.')
    if ranked:
        table = pd.DataFrame(ranked).rename(columns={
            'pickup_area': 'Pickup area', 'trip_count': 'Accepted trips',
            'recorded_trip_total_usd': 'Recorded revenue (USD)',
            'average_recorded_total_usd': 'Average amount per trip (USD)',
            'known_revenue_share_pct': 'Share of known-area revenue (%)',
            'trip_rank': 'Trip rank', 'revenue_rank': 'Revenue rank',
        })
        l, r = st.columns(2)
        with l:
            st.write('**Top 10 areas by recorded revenue**')
            chart(table.head(10), 'Pickup area', 'Recorded revenue (USD)', '#16897f', money=True)
        with r:
            st.write('**Top 10 areas by trip count**')
            volume = table.sort_values(['Accepted trips', 'Pickup area'], ascending=[False, True]).head(10)
            chart(volume, 'Pickup area', 'Accepted trips', '#385caa')
        st.write('**Every known area · compare amount, volume, and average**')
        view = table.copy()
        for col in ['Recorded revenue (USD)', 'Average amount per trip (USD)', 'Share of known-area revenue (%)']:
            view[col] = pd.to_numeric(view[col], errors='coerce')
        st.dataframe(view[['Revenue rank', 'Pickup area', 'Recorded revenue (USD)', 'Accepted trips',
                           'Average amount per trip (USD)', 'Share of known-area revenue (%)', 'Trip rank']],
                     hide_index=True, use_container_width=True,
                     column_config={
                         'Recorded revenue (USD)': st.column_config.NumberColumn(format='$%.2f'),
                         'Average amount per trip (USD)': st.column_config.NumberColumn(format='$%.2f'),
                         'Share of known-area revenue (%)': st.column_config.NumberColumn(format='%.2f%%'),
                     })
        st.caption('Averages are sums divided by counts over the entire interval. Small groups remain visible with their counts; a high observed average does not establish a persistent pattern. Exact ties share a rank.')
        st.download_button('↓ Download area comparison', table.to_csv(index=False),
                           'area_revenue_comparison.csv', 'text/csv')
    else:
        st.info('No accepted trips have a known pickup area.')
    st.subheader('What these records show')
    for insight in business_insights(summary):
        st.markdown('<div class="insight">' + escape(insight) + '</div>', unsafe_allow_html=True)

with day_tab:
    st.subheader('Recorded revenue by source trip date')
    plot = daily.copy()
    plot['Date'] = plot['trip_date'].astype(str)
    plot['Recorded revenue (USD)'] = plot['recorded_trip_total_usd'].astype(float)
    st.vega_lite_chart(plot[['Date', 'Recorded revenue (USD)']], {
        'height': 290, 'mark': {'type': 'bar', 'color': '#16897f', 'cornerRadiusEnd': 5},
        'encoding': {
            'x': {'field': 'Date', 'type': 'nominal', 'sort': 'ascending', 'axis': {'labelAngle': -35}},
            'y': {'field': 'Recorded revenue (USD)', 'type': 'quantitative', 'axis': {'format': '$,.0f'}},
            'tooltip': [{'field': 'Date', 'type': 'nominal'},
                        {'field': 'Recorded revenue (USD)', 'type': 'quantitative', 'format': '$,.2f'}],
        },
        'config': {'view': {'stroke': None}},
    }, use_container_width=True)
    if days['day_count'] == 1:
        st.info('This publication contains one date. Daily comparisons need a wider processed interval.')
    else:
        revenue_dates = ', '.join(str(r['trip_date']) for r in days['revenue_leaders'])
        busy_dates = ', '.join(str(r['trip_date']) for r in days['trip_leaders'])
        st.write(f'**Highest recorded revenue day(s):** {revenue_dates}.')
        st.write(f'**Most accepted trips day(s):** {busy_dates}.')
        st.caption('These are observed dates within this publication, not evidence of a recurring weekday pattern.')
    avg_duration = (daily['average_duration_minutes'] * daily['trip_count']).sum() / daily['trip_count'].sum()
    st.metric('Trip-weighted average reported duration', f'{avg_duration:.1f} min')
    daily_view = daily.copy()
    daily_view['average_recorded_amount_per_trip_usd'] = [
        Decimal(str(amount)) / int(n) for amount, n in zip(daily['recorded_trip_total_usd'], daily['trip_count'])
    ]
    st.dataframe(daily_view, hide_index=True, use_container_width=True)
    st.download_button('↓ Download daily metrics', daily_view.to_csv(index=False), 'daily_metrics.csv', 'text/csv')

with trust_tab:
    st.subheader('From downloaded records to published results')
    st.dataframe(pd.DataFrame([
        ('Downloaded rows', quality['raw']),
        ('Duplicates removed', quality['duplicates']),
        ('Rejected after deduplication', quality['rejected']),
        ('Accepted trips', quality['accepted']),
        ('Accepted trips with unknown pickup area', quality['unknown_pickup']),
        ('Accepted trips with zero reported duration', quality['zero_duration']),
    ], columns=['Measure', 'Rows']), hide_index=True, use_container_width=True)
    st.success(f"Count reconciliation: {quality['raw']:,} downloaded = {quality['duplicates']:,} duplicates + {quality['rejected']:,} rejected + {quality['accepted']:,} accepted.")
    if published['rerun_verified']:
        st.success('Rerun verified: the same captured source produced identical business results.')
    else:
        st.info('First publication for this source interval. A second successful run verifies repeatability.')
    if quality['rejection_reasons']:
        reasons = pd.DataFrame(list(quality['rejection_reasons'].items()), columns=['Reason', 'Flags'])
        st.write('**Rejection reasons**')
        st.dataframe(reasons, hide_index=True, use_container_width=True)
        st.caption('One rejected record can carry more than one flag.')
    st.write('**How to read the figures**')
    st.markdown(
        '- Revenue means the source-reported trip total for accepted records. Costs are not calculated.\n'
        '- Area is the pickup community-area code, not the destination or an exact street location.\n'
        '- Headline totals include unknown pickup areas; geographic rankings exclude them.\n'
        '- Revenue share in the area table uses known-area revenue as its denominator.\n'
        '- Average amount per trip uses total amount divided by trip count; zero amounts are retained.\n'
        '- Source timestamps are treated as local wall-clock values. Duration uses reported seconds.\n'
        '- Rejected records are retained separately and excluded from all business metrics.\n'
        '- Charts and percentages round values for display. Downloaded comparison amounts retain decimal arithmetic.\n'
        '- Findings describe the captured source and selected period; they are not forecasts.'
    )
    with st.expander('Published output references'):
        st.write('Gold output:', published['prefix'])
        st.write('Business fingerprint:', published['business_fingerprint'])
        st.download_button('↓ Download original daily-area gold metrics',
                           areas.to_csv(index=False), 'daily_area_gold.csv', 'text/csv')
st.caption('CHICAGO TAXI · Airflow orchestrates. PySpark transforms. Object storage preserves the data trail.')
