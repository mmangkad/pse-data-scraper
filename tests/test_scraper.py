from pse_data_scraper.scraper import parse_companies_from_html


def test_parse_companies_from_html_extracts_rows():
    html = """
    <table class="list">
      <tbody>
        <tr>
          <td><a onclick="cmDetail('123','456')">Acme Corporation</a></td>
          <td><a>ACME</a></td>
        </tr>
      </tbody>
    </table>
    """
    companies = parse_companies_from_html(html)

    assert len(companies) == 1
    company = companies[0]
    assert company.company_id == "123"
    assert company.security_id == "456"
    assert company.company_name == "Acme Corporation"
    assert company.stock_symbol == "ACME"
